## Postgres ENUM vs VARCHAR + Python Enum

Two approaches for status columns. Most teams use Option 2.

### Option 1 — Native Postgres ENUM (DB-enforced)
```python
from sqlalchemy import Enum as PgEnum

class Users(Base):
    status: Mapped[str] = mapped_column(
        PgEnum("active", "suspended", "closed", name="account_status"),
        nullable=False
    )
```
**Pros:** DB rejects invalid values at storage level — nothing bypasses it, even raw SQL scripts.  
**Cons:** Adding a new value requires `ALTER TYPE account_status ADD VALUE 'banned'` — cannot be rolled back. Alembic handling of enum changes is painful. Two sources of truth (Python enum + Postgres type) that must stay in sync.

### Option 2 — VARCHAR + Python Enum (most common in practice)
```python
class Users(Base):
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
```
**Pros:** Adding new values is just a Python change — no migration. Single source of truth. Simple migrations.  
**Cons:** DB accepts any string; a raw SQL insert could store `"actve"` silently.

### Best of both: VARCHAR + CheckConstraint
Gives DB-level validation without the rigidity of a native enum type:
```python
class Users(Base):
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'closed')",
            name="ck_users_status"
        ),
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
```
This is the recommended pattern for this project — validation at Python (Pydantic), at the service layer, and at the DB via CheckConstraint. Status changes that add new values only need a Python + migration change, not a painful `ALTER TYPE`.

---

#### diff between Mapped and mapped_column

- `Mapped` is used to declare the type of a mapped attribute in SQLAlchemy ORM.
- `mapped_column` is used to define the column properties for the mapped attribute (in database schema).

### Indexing and Constraints
- by defult whenever unique = true or primary_key = true is set, an index is created automatically.
- If you want to create an index without setting unique or primary_key, you can use the `index=True` parameter in `mapped_column`.
- use Index() to create a composite index on multiple columns. eg: Index('my_index', MyModel.column1, MyModel.column2)
- You can also define constraints like `CheckConstraint`, `UniqueConstraint`, and `ForeignKeyConstraint` to enforce rules on the data in the database. eg: 
```python
from sqlalchemy import CheckConstraint, UniqueConstraint, ForeignKeyConstraint
class MyModel(Base):
    __tablename__ = 'my_model'
    id = mapped_column(Integer, primary_key=True)
    value = mapped_column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint('value >= 0', name='check_value_positive'),
        UniqueConstraint('value', name='unique_value'),
        ForeignKeyConstraint(['other_id'], ['other_table.id'], name='fk_other_id'),
    )
```
- both index and constraints can be defined in `__table_args__` as a tuple or list.
- ForeignKey does not auto-create an index in PostgreSQL - we have to do it explicitly.

# default timestamp and SQLAlchemy "func"
- defult timestamp can be set using `server_default` parameter in `mapped_column`. Alsu usefrom sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP with timezone=True for PostgreSQL timestamp with timezone support.
- It stores the current timestamp when a new record is inserted into the database with `server_default=func.now()`.

### default values
- UUID: `default=uuid.uuid4` This will generate a new UUID for each new record.
- String: `default='default_value'` This will set a default string value for the column.
- Integer: `default=0` This will set a default integer value for the column.

Where to use what Decimal vs Integer vs Float
- Use `Integer` for whole numbers without decimal points.
- Use `Float` for approximate decimal numbers, but be cautious of precision issues.
- Use `Decimal` for exact decimal numbers, especially for financial calculations where precision is crucial.

### ForeignKey and relationship
- `ForeignKey` is used to define a foreign key constraint on a column, linking it to another table's primary key.
- `relationship` is used to define the relationship between two mapped classes, allowing for easy access to related objects in the ORM.
- `back_populates` is used to define a bidirectional relationship between two mapped classes, allowing for easy navigation in both directions.
- we could also use `backref` to create a bidirectional relationship, but it is less explicit than `back_populates`.

#### On Delete and On Update
- `ondelete` and `onupdate` parameters in `ForeignKey` specify the behavior when the referenced record is deleted or updated. Common options include:
  - `CASCADE`: Automatically delete or update the related records.
  - `SET NULL`: Set the foreign key to NULL when the referenced record is deleted or updated.
  - `RESTRICT`: Prevent deletion or update of the referenced record if there are related records.

#### Composite Primary Key
- A composite primary key is a primary key that consists of multiple columns. It can be defined using the `PrimaryKeyConstraint` in the `__table_args__` of a mapped class.

---

## Circular Imports — TYPE_CHECKING pattern

When two models reference each other (User has orders, Order has customer), you get a circular import:

```
users.py imports Order → orders.py imports User → back to users.py → crash
```

The fix is `TYPE_CHECKING` — a flag that is `False` at runtime but `True` only when a type checker (mypy, pyright) runs. Imports inside the guard are never actually executed at runtime:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.orders import Order   # never runs at runtime, only for type hints

class User(Base):
    orders: Mapped[list["Order"]] = relationship(...)  # string reference — resolved lazily
```

Use string `"Order"` in `relationship()` and `Mapped["Order"]` so SQLAlchemy resolves the class name at runtime without needing the import. This is the standard pattern for all bidirectional relationships.

---

## server_default vs default

Both set a value when no value is provided, but they run in different places:

| | `server_default` | `default` |
|---|---|---|
| Where it runs | Inside PostgreSQL (SQL expression) | Inside Python before INSERT |
| Works for raw SQL? | Yes | No — bypassed entirely |
| Migration | Shows up in Alembic as a DB-level default | Not visible in DB schema |
| Example | `server_default="0"`, `server_default=func.now()` | `default=uuid.uuid4`, `default=Decimal("0")` |

For timestamps and financial defaults, prefer `server_default`. For UUID generation, use `default=uuid.uuid4` (Python-side is fine — the DB doesn't need to generate it).

---

## onupdate=func.now() — the caveat

```python
updated_at: Mapped[datetime] = mapped_column(
    PG_TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
)
```

`onupdate` works **only via the SQLAlchemy ORM**. If anyone runs a raw SQL UPDATE against the table (a migration script, a manual fix, another service), `updated_at` will NOT be refreshed. For truly reliable `updated_at`, you need a PostgreSQL trigger:

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_orders_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

For this project, `onupdate=func.now()` is fine. In production, the trigger is safer.

---

## cascade="all, delete-orphan" on relationships

```python
line_items: Mapped[list["OrderLineItem"]] = relationship(
    "OrderLineItem", back_populates="order", cascade="all, delete-orphan"
)
```

When you delete an `Order`, SQLAlchemy automatically deletes all its `OrderLineItem` rows too. Without this, you'd get a foreign key violation (order_id references a deleted order).

Use `cascade="all, delete-orphan"` only for **composition** (the child cannot exist without the parent — a line item without an order is meaningless). Do NOT use it for references (a Payment should not be auto-deleted when an order is deleted — you need those records).

---

## uselist=False — one-to-one relationships

```python
shipment: Mapped[Optional["Shipment"]] = relationship(
    "Shipment", back_populates="order", uselist=False
)
```

By default, `relationship()` returns a list. `uselist=False` tells SQLAlchemy this is a single object (one-to-one). Access it as `order.shipment`, not `order.shipments[0]`. The DB-level uniqueness is enforced by `unique=True` on the FK column in the Shipment model.

---

## JSONB vs JSON in PostgreSQL

Both store JSON data, but they are different:

| | `JSON` | `JSONB` |
|---|---|---|
| Storage | Text (raw string) | Binary (parsed) |
| Duplicate keys | Preserved | Last value wins |
| Whitespace | Preserved | Stripped |
| Indexing | Not supported | Can index specific keys with GIN index |
| Query speed | Slower (re-parses every time) | Faster |

Always use `JSONB` for event payloads and any JSON you will query or filter on. Use `JSON` only if you need to preserve exact formatting (almost never).

```python
from sqlalchemy.dialects.postgresql import JSONB
payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

---

## mapped_column — default vs server_default vs onupdate

```python
# default — Python executes this before sending INSERT to DB
id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)      # function reference, called each time
status: Mapped[str]   = mapped_column(default="active")        # plain value

# server_default — raw SQL sent to DB as part of column definition
created_at: Mapped[datetime] = mapped_column(server_default=func.now())  # DB fills it in
total_spent: Mapped[Decimal] = mapped_column(server_default="0")         # SQL literal "0"

# onupdate — Python-side, fires before any UPDATE via the ORM
updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

**When each one runs:**

| param | when | bypassed by raw SQL? |
|---|---|---|
| `default` | Python, before INSERT | Yes — raw SQL skips Python entirely |
| `server_default` | DB, inside INSERT statement | No — the DB applies it |
| `onupdate` | Python, before ORM UPDATE | Yes — raw SQL bypasses it |

**Rule of thumb:**
- UUIDs → `default=uuid.uuid4` (Python generates it, that's fine)
- Timestamps, numeric defaults → `server_default` (DB is authoritative)
- `updated_at` → `onupdate=func.now()` is acceptable for ORM-only projects; use a DB trigger if anything else writes to the table

---

## relationship() — all the flags explained

### back_populates vs backref

Both create a bidirectional relationship. The difference is explicitness.

```python
# back_populates — you declare both sides manually (preferred)
class User(Base):
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")

class Order(Base):
    customer: Mapped["User"] = relationship("User", back_populates="orders")
```

```python
# backref — you declare only one side; SQLAlchemy creates the other automatically
class User(Base):
    orders: Mapped[list["Order"]] = relationship("Order", backref="customer")
# Order.customer now exists automatically — but it's invisible in Order's code
```

**Use `back_populates` always.** `backref` looks shorter but hides half the relationship from the reader. When someone reads `Order`, they don't see `customer` is there.

---

### cascade

Controls what SQLAlchemy does to child objects when the parent is modified via the ORM session.

```python
relationship("OrderLineItem", cascade="all, delete-orphan")
```

| value | meaning |
|---|---|
| `"save-update, merge"` | default — child is tracked in session when parent is |
| `"all"` | save-update + merge + delete + expunge + refresh |
| `"delete"` | delete children when parent is deleted |
| `"delete-orphan"` | delete children that are removed from the collection (even without deleting parent) |
| `"all, delete-orphan"` | most common for composition — full ownership |

```python
# With delete-orphan: removing an item from the list deletes it from DB
order.line_items.remove(item)   # item gets deleted from DB on commit
# Without delete-orphan: removing from list just clears the FK, item stays in DB
```

**Use `cascade="all, delete-orphan"` only for composition** — where the child cannot exist without the parent (line items without an order, address without a user). Do NOT use it for associations (payments, events).

---

### uselist

```python
# one-to-many (default) — uselist=True implicitly
orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")

# one-to-one — uselist=False
shipment: Mapped[Optional["Shipment"]] = relationship("Shipment", back_populates="order", uselist=False)
```

With `uselist=False`, accessing `order.shipment` returns a single object or `None`, not a list. The DB constraint (`unique=True` on the FK) enforces the one-to-one at storage level; `uselist=False` just tells the ORM how to present it.

---

### lazy — loading strategy

This controls **when** SQLAlchemy fetches related objects from the DB.

```python
relationship("Order", lazy="select")       # default
relationship("Order", lazy="joined")
relationship("Order", lazy="selectin")
relationship("Order", lazy="raise")
```

| strategy | what happens | use when |
|---|---|---|
| `"select"` (default) | separate SQL query fired when you access `.orders` | simple cases, small collections |
| `"joined"` | JOIN in the original query | always need the related object with the parent |
| `"selectin"` | one extra `SELECT ... WHERE id IN (...)` for all parents at once | collections — avoids N+1 |
| `"raise"` | raises error if accessed without explicit eager load | enforcing no accidental lazy loads in performance-sensitive code |
| `"noload"` | never loads, returns empty | when you never need the relationship |

**The N+1 problem** — the main reason lazy loading matters:
```python
# lazy="select" (default) — fires 1 + N queries
users = db.query(User).all()          # 1 query: SELECT * FROM users
for user in users:
    print(user.orders)                # N queries: SELECT * FROM orders WHERE user_id = ?
                                      # one per user — 1000 users = 1001 queries

# lazy="selectin" — fires 2 queries total
users = db.query(User).options(selectinload(User.orders)).all()
# query 1: SELECT * FROM users
# query 2: SELECT * FROM orders WHERE user_id IN (1, 2, 3, ..., 1000)
```

For most FastAPI endpoints where you return a response with nested data, use `selectinload()` or `joinedload()` explicitly in the query rather than relying on the default lazy strategy.

---

## ondelete in ForeignKey vs cascade in relationship — the important distinction

These look like they do the same thing but they operate at completely different levels.

```python
# FK ondelete — a PostgreSQL instruction
order_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("orders.id", ondelete="CASCADE")
)

# relationship cascade — a SQLAlchemy ORM instruction
line_items = relationship("OrderLineItem", cascade="all, delete-orphan")
```

| | FK `ondelete` | relationship `cascade` |
|---|---|---|
| Who executes it | PostgreSQL | SQLAlchemy Python ORM |
| Triggered by | Any DELETE on the parent row (raw SQL, migrations, other services) | Only ORM `session.delete(parent)` |
| Raw SQL bypass | No — DB always enforces it | Yes — raw SQL ignores ORM cascade |
| Performance | Fast — single DB operation | Slower — ORM may load then delete children one by one |

**When to combine them:** If you use `ondelete="CASCADE"` on the FK, tell SQLAlchemy not to also emit its own DELETEs by adding `passive_deletes=True`:

```python
line_items = relationship(
    "OrderLineItem",
    cascade="all, delete-orphan",
    passive_deletes=True        # "trust the DB to handle deletes, don't load children first"
)
order_id = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
```

Without `passive_deletes=True`, SQLAlchemy loads all children into memory before deleting them — wasteful if there are thousands.

**Summary for this project:**
- `ondelete="RESTRICT"` on customer → order FK: DB prevents deleting a customer who has orders
- `ondelete="CASCADE"` + `passive_deletes=True` on order → line_items: DB deletes line items when order is deleted, ORM trusts the DB to do it