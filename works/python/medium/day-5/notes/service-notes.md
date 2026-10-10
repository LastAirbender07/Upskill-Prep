# Service Layer Notes

## What the service layer is

The service layer sits between the route (HTTP) and the CRUD layer (DB).
Its only job is business logic. It knows the rules of the domain — CRUD does not.

```
Route       — HTTP in/out, serialize/deserialize, HTTP status codes
   ↓
Service     — business rules, state machines, cross-entity coordination
   ↓
CRUD        — DB reads/writes, no business decisions
   ↓
PostgreSQL
```

---

## The single most important rule

**Service layer enforces the rules. CRUD just executes.**

CRUD asks: "Can I physically write this to the DB?"
Service asks: "Am I *allowed* to do this given the current state of the system?"

If you see business conditions (user is active, order is cancellable, stock > 0) inside a CRUD
method — move them up to the service.

---

## Service class structure

```python
class ProductService:
    def __init__(self, db: Session):
        self.repo = ProductRepository(db)   # service owns the repo, not the session directly
```

The service receives a `Session` from the route (via FastAPI's dependency injection),
creates the repo internally. You could also inject the repo directly — either way,
the session must come from outside (never create a session inside a service).

---

## Pre-check vs catch IntegrityError

Two strategies for handling constraint violations:

### Strategy A — pre-check in service (preferred for UX)
```python
def create_product(self, data: ProductCreate) -> ProductResponse:
    existing = self.repo.get_by_sku(data.sku)
    if existing:
        raise ValueError(f"A product with SKU '{data.sku}' already exists")
    return self.repo.create_product(data)
```

### Strategy B — let CRUD catch IntegrityError
```python
# CRUD already does this:
try:
    self.db.commit()
except IntegrityError as e:
    raise ValueError("...") from e
```

Both work. The difference:
- Pre-check = one extra SELECT, but gives a human-readable, business-domain error message
- IntegrityError catch = no extra SELECT, but the error message is more technical

For fields like `email` or `sku` where users need clear feedback, pre-check is better.
For constraints that should never fail in normal usage, rely on IntegrityError.

**Race condition note:** Even with a pre-check, a duplicate can sneak through under
high concurrency (two requests pass the check at the same time). The IntegrityError
catch in CRUD is still the final safety net. Pre-check is for UX, not correctness.

---

## Existence check before update/delete

Always verify a record exists before updating or deleting it.
Return or raise accordingly — don't do a silent no-op.

```python
def update_product(self, product_id: UUID, data: ProductUpdate) -> ProductResponse:
    existing = self.repo.get_by_id(product_id)
    if existing is None:
        raise ValueError(f"Product {product_id} not found")   # route converts to 404
    ...
```

Why not just let CRUD handle it? CRUD already returns `None` if not found.
But the service is the right place to decide what "not found" means for the business operation
(raise an error, return a default, trigger a fallback — depends on context).

---

## Dedicated transition methods vs generic update

For status changes, prefer dedicated methods over `update({"status": "..."})`:

```python
# generic — works but caller can set any status they want
def update_product(self, product_id, data: ProductUpdate): ...

# dedicated — encapsulates the transition and its rules
def discontinue_product(self, product_id: UUID) -> ProductResponse:
    existing = self.repo.get_by_id(product_id)
    if existing.status == ProductStatus.discontinued:
        raise ValueError("Already discontinued")   # guard: idempotent check
    return self.repo.update_product(product_id, {"status": "discontinued"})
```

For simple entities (Product) the difference is minor.
For state machine entities (Order, Payment, Shipment) this becomes critical:
a generic `update_status` call on an Order could skip the transition validation entirely.

---

## Enum value vs enum member — the .value trap

ORM columns that store enums as strings (e.g. `String(20)` with `server_default="available"`)
need the enum's `.value` (a string), not the enum member itself:

```python
# WRONG — passes the enum member object, not the string "discontinued"
self.repo.update_product(product_id, {"status": ProductStatus.discontinued})

# CORRECT — passes the string "discontinued"
self.repo.update_product(product_id, {"status": ProductStatus.discontinued.value})
```

This trips up almost everyone the first time.
The fix: when calling CRUD, always convert enum → `.value` before putting it in a dict.

Alternatively, use SQLAlchemy's `Enum(ProductStatus)` column type — then SQLAlchemy
handles the conversion automatically. But that requires the enum to be registered in the DB schema.

---

## exclude_unset in service-to-CRUD updates

When the service calls `model_dump(exclude_unset=True)` and passes the result to CRUD,
only the fields the caller actually provided are written. This is PATCH semantics:

```python
update_dict = data.model_dump(exclude_unset=True)
# caller sent: {"name": "New Name"}
# update_dict = {"name": "New Name"}   ← price, category etc. untouched
updated = self.repo.update_product(product_id, update_dict)
```

If you use `model_dump()` without `exclude_unset`, every field that was `None` in the
update schema will overwrite the existing value in DB with NULL.

---

## Cross-field validation in service

Pydantic validates individual fields. The service validates relationships between fields
or between the incoming data and the current DB state:

```python
def restock(self, product_id: UUID, quantity: int) -> ProductResponse:
    if quantity <= 0:
        raise ValueError("Restock quantity must be > 0")   # field rule

    product = self.repo.get_by_id(product_id)
    if product.status == ProductStatus.discontinued:
        raise ValueError("Cannot restock a discontinued product")   # state rule
```

The first check is a field rule — could also be in Pydantic schema with `Field(gt=0)`.
The second check is a state rule — requires knowing the current DB state, so it lives here.

---

## Side effects in service methods

Service methods often do more than one thing. That's intentional — they coordinate.

Example: `restock` does two things atomically:
1. Updates stock_quantity
2. Updates status (out_of_stock → available if applicable)

Both go into a single `update_product(dict)` call — single DB round trip, single commit.

More complex example — `confirm_payment` does four things atomically:
1. Marks payment completed
2. Updates order status to `confirmed`
3. Increments `user.total_spent`
4. Writes a `payment_completed` event log entry

When side effects span multiple CRUD repositories, the service coordinates them.
All repos share the same session — so all writes commit together or roll back together.

---

## State machines — encoding transitions as a dict

For entities with a state machine (Order, Payment, Shipment), encode the allowed transitions
as a module-level dict rather than scattered `if` checks:

```python
_VALID_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.pending:    {PaymentStatus.processing},
    PaymentStatus.processing: {PaymentStatus.completed, PaymentStatus.failed},
    PaymentStatus.failed:     {PaymentStatus.pending},    # retry path
    PaymentStatus.completed:  {PaymentStatus.refunded},
    PaymentStatus.refunded:   set(),                      # terminal — empty set
}
```

Terminal states map to `set()`. This makes them self-documenting: if you see `set()`,
that state has no exit. No special-casing needed.

Pair it with a private `_assert_transition` helper:

```python
def _assert_transition(self, current: PaymentStatus, target: PaymentStatus) -> None:
    if target not in _VALID_TRANSITIONS[current]:
        allowed = {s.value for s in _VALID_TRANSITIONS[current]}
        raise ValueError(
            f"Cannot transition from '{current.value}' to '{target.value}'. "
            f"Allowed: {allowed or 'none (terminal state)'}"
        )
```

Every dedicated transition method calls `_assert_transition` before touching the DB:

```python
def confirm_payment(self, payment_id, transaction_ref):
    payment = self.repo.get_by_id(payment_id)
    self._assert_transition(payment.status, PaymentStatus.completed)   # guard first
    return self.repo.update_status(payment_id, PaymentStatus.completed, ...)
```

The underscore prefix on `_assert_transition` marks it as internal — callers of the
service should never call it directly.

---

## Multiple repositories in one service

When a service method needs to coordinate across entities, inject all required repos
in `__init__`:

```python
class PaymentService:
    def __init__(self, db: Session):
        self.repo = PaymentRepository(db)
        self.order_repo = OrderRepository(db)
        self.user_repo = UsersRepository(db)
        self.event_repo = EventLogRepository(db)
```

All repos share the same `db` session — this is what makes them transactional.
When `confirm_payment` updates the payment, then the order, then the user's total_spent,
all three writes are in the same session and committed together.

**Don't inject other services into a service.** If `PaymentService` needs to update an
order, it calls `OrderRepository` directly — not `OrderService`. Service-to-service calls
create circular dependencies and hidden side-effect chains. Services call repos, not each other.

---

## Side effect ordering in multi-step service methods

When a method has multiple side effects, order matters:

```python
def confirm_payment(self, payment_id, transaction_ref):
    # 1. validate first — fail fast before any writes
    payment = self.repo.get_by_id(payment_id)
    self._assert_transition(payment.status, PaymentStatus.completed)

    # 2. primary write — the thing being confirmed
    updated = self.repo.update_status(payment_id, PaymentStatus.completed, ...)

    # 3. cascade writes — downstream state changes triggered by the primary
    order = self.order_repo.get_by_id(payment.order_id)
    self.order_repo.update_status(payment.order_id, OrderStatus.confirmed)

    # 4. denormalized field update — derived data that must stay in sync
    self.user_repo.update_total_spent(order.user_id, order.final_amount)

    # 5. event log — always last, audit trail of what just happened
    self.event_repo.create_event(EventType.payment_completed, ...)

    return updated   # return the primary object, not a side effect
```

Rules:
- Validate before any write — if the guard fails, nothing should have changed
- Return the primary object the caller asked about (`updated` payment, not the order)
- Event log is always last — it records what happened, so it goes after everything happened

---

## What the service raises vs what the route catches

Services raise `ValueError` (and sometimes custom exceptions).
Routes catch these and convert to HTTP responses:

```
ValueError("Product not found")    → HTTP 404
ValueError("SKU already taken")    → HTTP 409 Conflict
ValueError("Cannot restock discontinued") → HTTP 422 Unprocessable
```

The service doesn't know about HTTP status codes — that's the route's job.
Keep that boundary clean: service raises domain errors, route translates to HTTP.

---

## Logging in service vs CRUD

Both layers log, but for different purposes:

- **CRUD logs:** "what DB operation happened" — `Created product abc123`
- **Service logs:** "what business event happened" — `Product abc123 (SHOE-RED-42) marked as discontinued`

Service logs include business context (SKU, user, reason).
CRUD logs are more technical (IDs, table names, row counts).
