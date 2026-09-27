# CRUD Layer Notes

## What is the CRUD layer

CRUD (Create, Read, Update, Delete) is the layer that talks directly to the database.
It has one job: execute DB operations. Nothing else.

```
Route (HTTP)
   ↓
Service (business logic)
   ↓
CRUD / Repository (DB operations)   ← you are here
   ↓
PostgreSQL
```

---

## The single most important rule

**CRUD asks no questions. It just does what it is told.**

No `if user is suspended` checks. No `if stock > 0`. No business decisions.
Those belong in the service layer.

If you find an `if` statement in CRUD that checks business state — move it up to the service.

The only `if` that belongs in CRUD:
- `if orm_object is None: return None` — checking whether the DB returned a row

---

## Pydantic → ORM (for writes)

`model_dump()` converts a Pydantic object to a plain Python dict.
Unpack that dict as keyword arguments into the SQLAlchemy ORM constructor:

```python
user_orm = User(**user_create.model_dump())
```

This works because your ORM column names match your Pydantic field names.
If they don't match, you'd need to map manually or use aliases.

---

## ORM → Pydantic (for reads / responses)

`model_validate()` converts an ORM object to a Pydantic model.
This works only because the response schema has `from_attributes=True` in its config:

```python
# in the schema
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ...

# in CRUD
return UserResponse.model_validate(user_orm)
```

Without `from_attributes=True`, Pydantic expects a dict, not an ORM object, and raises an error.

---

## db.refresh() — why it matters

After `db.commit()`, the ORM object in memory may be stale.
`server_default` values (id, registration_date, status) are set by PostgreSQL during the INSERT,
not by Python. After commit, the Python object doesn't have those values yet.

`db.refresh(user_orm)` fires a `SELECT` to pull the latest DB state back into the object:

```python
self.db.add(user_orm)
self.db.commit()
self.db.refresh(user_orm)   # now user_orm.id, .registration_date etc. are populated
```

Skip this and you'll return a response with `None` for server-generated fields.

---

## exclude_unset=True — for PATCH / partial updates

`model_dump()` by default includes ALL fields, even ones not provided (they get their defaults).
For a PATCH update, you only want to update what the caller actually sent.

```python
# caller sends: {"full_name": "John"}
# without exclude_unset — overwrites phone_number with None even though caller didn't touch it
update_dict = update_data.model_dump()
# → {"full_name": "John", "phone_number": None}

# with exclude_unset — only what was actually provided
update_dict = update_data.model_dump(exclude_unset=True)
# → {"full_name": "John"}
```

Always use `exclude_unset=True` when applying partial updates via `setattr`:

```python
for field, value in update_dict.items():
    setattr(user_orm, field, value)
```

---

## IntegrityError — what triggers it and what to do

PostgreSQL raises an `IntegrityError` (via SQLAlchemy) when a DB constraint is violated:
- `unique=True` column gets a duplicate value (e.g. email already exists)
- `nullable=False` column gets NULL
- FK constraint violation (referencing a non-existent row)
- `CheckConstraint` violated

Pattern:
```python
try:
    self.db.commit()
except IntegrityError as e:
    self.db.rollback()          # MUST rollback before any further DB operations
    raise ValueError("...") from e
```

Always rollback before re-raising. If you don't, the session is in a broken state and
subsequent queries on the same session will fail.

---

## skip / limit — pagination

Never return all rows from a large table without limits.

```python
def get_all(self, skip: int = 0, limit: int = 100) -> list[UserResponse]:
    return self.db.query(User).offset(skip).limit(limit).all()
```

- `offset(skip)` — skip the first N rows
- `limit(limit)` — return at most N rows
- Caller passes `skip=0, limit=20` for page 1; `skip=20, limit=20` for page 2

---

## CRUD returns: ORM objects or Pydantic?

Two valid patterns in practice:

### Pattern A — CRUD returns Pydantic (what we use here)
```python
def get_by_id(self, user_id) -> UserResponse | None:
    orm = self.db.query(User).filter(User.id == user_id).first()
    return UserResponse.model_validate(orm) if orm else None
```
Clean. Service layer just passes responses through or raises errors.
Downside: if the service needs to modify the ORM object (e.g. change status before commit),
it can't — it only has the Pydantic response, not the live ORM object.

### Pattern B — CRUD returns ORM objects
```python
def get_by_id(self, user_id) -> User | None:
    return self.db.query(User).filter(User.id == user_id).first()
```
Service layer gets the raw ORM object, can mutate it directly, then converts to Pydantic
at the route layer.
More flexible for complex service operations (state changes, multi-step writes).

**For this project:** CRUD returns Pydantic for reads, but internally holds ORM objects
for writes. When a service needs to mutate something, we'll add internal methods that
return ORM objects.

---

## Session management — where the session comes from

The `db: Session` is injected via FastAPI's dependency injection:

```python
# database.py
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# route
@router.post("/users")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    repo = UsersRepository(db)
    return repo.create_user(user)
```

One session per request. The session is created when the request starts and closed when it ends.
Never create a session inside CRUD — always receive it from outside (dependency injection).

---

## Repository pattern vs plain functions

Two styles you'll see in the wild:

### Class-based (Repository pattern) — what we use
```python
class UsersRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, data): ...
    def get_by_id(self, id): ...
```

### Function-based
```python
def create_user(db: Session, data: UserCreate): ...
def get_user_by_id(db: Session, user_id): ...
```

Both are valid. Class-based groups related operations together and avoids passing `db`
to every function. Function-based is simpler for small projects.

---

## db.flush() vs db.commit()

`flush()` sends the SQL to PostgreSQL within the current transaction but does NOT commit it.
The change is visible to the current session but not to other sessions yet.

```python
order_orm = Order(user_id=user_id, ...)
self.db.add(order_orm)
self.db.flush()         # INSERT fires, order_orm.id is now populated from DB
                        # but transaction is still open — nothing is permanent yet

line_item = OrderLineItem(order_id=order_orm.id, ...)   # can use the id now
self.db.add(line_item)

self.db.commit()        # both order + line items committed atomically
```

Use `flush()` when:
- You need a DB-generated value (like `id`) to use in a related insert
- You want multiple inserts to be part of the same atomic transaction

If any step after `flush()` fails, `rollback()` undoes everything including the flushed insert.

---

## selectinload vs joinedload — solving the N+1 problem

When you fetch an order, you usually need its line items too.
Without eager loading, accessing `order.line_items` fires a separate SQL query — one per order.

```python
orders = db.query(Order).all()      # 1 query
for order in orders:
    print(order.line_items)         # 1 query per order = N+1 total queries
```

### selectinload — fires a second SELECT with IN clause

```python
from sqlalchemy.orm import selectinload

orders = (
    db.query(Order)
    .options(selectinload(Order.line_items))
    .all()
)
# query 1: SELECT * FROM orders
# query 2: SELECT * FROM order_line_items WHERE order_id IN (id1, id2, id3, ...)
# total: 2 queries regardless of how many orders
```

### joinedload — adds a JOIN to the original query

```python
from sqlalchemy.orm import joinedload

order = (
    db.query(Order)
    .options(joinedload(Order.user))
    .filter(Order.id == order_id)
    .first()
)
# single query: SELECT orders.*, users.* FROM orders LEFT JOIN users ON ...
```

### Why NOT to use joinedload on collections

`joinedload` on a one-to-many relationship causes **row multiplication**.
If an order has 5 line items, that order's columns are repeated 5 times in the result set.
SQLAlchemy deduplicates it in Python — but you already transferred 5x the data over the wire.

```
order with 3 line items  → JOIN returns 3 rows for that order
order with 10 line items → JOIN returns 10 rows for that order
1000 orders, avg 15 items → 15,000 rows returned, deduplicated to 1000 in Python
```

`selectinload` avoids this entirely — fetches orders (1000 rows), then all line items
in one shot (15,000 rows total, already structured correctly, no duplication).

### Rule

```
selectinload → collections (one-to-many)          Order.line_items, User.orders
joinedload   → single objects (many-to-one, one-to-one)   Order.user, Order.shipment
```

For single objects there is no row multiplication risk — one order has exactly one user,
so the JOIN adds one row's worth of extra columns. `joinedload` is efficient there.

---

## When NOT to catch IntegrityError

Not every CRUD method needs a try/except. Only catch when there is a real, known constraint
that could be violated by normal usage:

| operation | catch? | reason |
|---|---|---|
| `create_user` | yes | email unique constraint |
| `create_payment` | yes | transaction_ref unique constraint |
| `delete_user` | yes | orders FK has RESTRICT |
| `create_event_log` | no | no unique constraints at all |
| `get_by_id` | no | SELECT cannot violate constraints |

If you catch `IntegrityError` on a table that has no constraints that could be violated,
you're hiding real bugs. Let unexpected DB errors propagate — they should never happen
in normal usage and you want to see them.

---

## Filtering in SQL, not in Python

Always push filtering into the SQL query. Never fetch all rows and filter in Python.

```python
# WRONG — fetches all shipments, filters in Python memory
all_shipments = db.query(Shipment).all()
overdue = [s for s in all_shipments if s.estimated_delivery_date < date.today()]

# CORRECT — only overdue rows come back over the wire
from sqlalchemy import func
overdue = (
    db.query(Shipment)
    .filter(Shipment.estimated_delivery_date < func.current_date())
    .all()
)
```

### Why SQL filtering is faster — the full pipeline

You asked: "internally PostgreSQL also needs to load 5 million rows and then check this, right?"

No — that's the key insight. PostgreSQL does NOT load 5 million rows when there's an index.

**Without an index (full table scan):**
```
disk → read 5M rows → check each date → return 200 matching rows
```
PostgreSQL reads every page of the table. But it still does the comparison inside the DB engine
(fast C code, no serialization) and returns only 200 rows to Python.

**With an index on estimated_delivery_date:**
```
disk → read index → jump directly to rows where date < today → return 200 matching rows
```
PostgreSQL reads only the index pages (much smaller than the full table) and jumps directly
to matching rows. Most of the 5M rows are never touched at all.

**Python filtering (wrong approach) — regardless of whether DB has an index:**
```
disk → read 5M rows → serialize to bytes → send over socket → deserialize into 5M Python objects
    → Python checks each object's date attribute → return 200 objects
```

The extra cost is in serialization and object creation:
- PostgreSQL serializes all 5M rows to wire format
- All 5M rows cross the network/socket between DB and app server
- SQLAlchemy deserializes 5M rows into 5M Python ORM objects (each with ~20 attributes)
- Python iterates and filters — gets 200 objects
- Python garbage-collects 4,999,800 objects

Every step costs time and memory. SQL filtering eliminates all of it — only the 200 matching
rows ever cross the wire, and only 200 Python objects are ever created.

`func.current_date()` runs the date comparison **inside PostgreSQL's process**, where
the data already lives. No serialization, no network, no Python object creation for the rejects.

---

## get_orm_by_id — when CRUD needs to return ORM objects

Most CRUD methods return Pydantic responses. But the service layer sometimes needs the raw
ORM object to mutate it directly (change status, update fields, then commit).

Pattern: add an internal method alongside the normal Pydantic-returning one:

```python
def get_by_id(self, order_id: UUID) -> OrderResponse | None:
    # for routes and external callers — returns serialized response
    orm = self.db.query(Order).filter(Order.id == order_id).first()
    return OrderResponse.model_validate(orm) if orm else None

def get_orm_by_id(self, order_id: UUID) -> Order | None:
    # for service layer — returns live ORM object for mutation
    return self.db.query(Order).filter(Order.id == order_id).first()
```

The service calls `get_orm_by_id`, mutates the object, commits, then calls `get_by_id`
to return the final Pydantic response to the route.

---

## update_status — dedicated methods vs generic update

For state machine entities (Order, Payment, Shipment), prefer dedicated `update_status()`
methods over a generic `update(fields: dict)`.

```python
# generic — CRUD doesn't know what's changing, service has full control
def update_product(self, product_id, update_data: dict) -> ProductResponse | None:
    ...

# dedicated — for state machine transitions where the column change has meaning
def update_status(self, order_id, new_status: OrderStatus) -> OrderResponse | None:
    ...
```

Dedicated methods make it explicit what CRUD is allowed to change. A generic update on
orders could accidentally allow the CRUD layer to set any field — the state machine
transition logic would have to live in every caller instead of being centralized.
