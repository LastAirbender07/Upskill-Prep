# SQLAlchemy Query Notes

## Three levels of query API

SQLAlchemy has three ways to write queries. You need to know all three.

```
Level 1: ORM (session.query)         → what we use for CRUD
Level 2: Core (select())             → for CTEs, window functions, complex analytics
Level 3: Raw SQL (text())            → last resort; for queries that are hard to express in SQLAlchemy
```

Rules:
- Standard CRUD (get_by_id, get_all, filter by status) → `session.query()`
- Aggregates, GROUP BY, CTEs, window functions → SQLAlchemy Core `select()`
- Extremely complex queries (running totals, cohort analysis) → `text()` with bound params

---

## Aggregates — COUNT, SUM, MAX, MIN, AVG

All aggregate functions live in `sqlalchemy.func`:

```python
from sqlalchemy import func

# count all orders
count = self.db.query(func.count(Order.id)).scalar()

# sum of final amounts for completed orders
total = (
    self.db.query(func.sum(Order.final_amount))
    .filter(Order.status == OrderStatus.completed)
    .scalar()   # .scalar() returns a single value, not a row
)

# multiple aggregates in one query
row = (
    self.db.query(
        func.count(Order.id).label("order_count"),
        func.sum(Order.final_amount).label("total_revenue"),
        func.avg(Order.final_amount).label("avg_order_value"),
        func.max(Order.created_at).label("last_order_date"),
    )
    .filter(Order.user_id == user_id)
    .one()   # .one() returns a single Row object (named tuple)
)

print(row.order_count, row.total_revenue)
```

`.scalar()` → single value. `.one()` → single row. `.all()` → list of rows.

---

## GROUP BY

Pair aggregates with `.group_by()` to compute per-group results:

```python
# daily order count and revenue
from sqlalchemy import func

rows = (
    self.db.query(
        func.date_trunc("day", Order.created_at).label("day"),
        func.count(Order.id).label("order_count"),
        func.sum(Order.final_amount).label("revenue"),
    )
    .filter(Order.created_at >= start_date)
    .group_by(func.date_trunc("day", Order.created_at))
    .order_by(func.date_trunc("day", Order.created_at))
    .all()
)

for row in rows:
    print(row.day, row.order_count, row.revenue)
```

### HAVING — filtering on aggregated values

`.having()` is `WHERE` applied after aggregation:

```python
# customers with more than 3 failed payments
from sqlalchemy import func

rows = (
    self.db.query(
        Payment.order_id,
        func.count(Payment.id).label("fail_count"),
    )
    .filter(Payment.status == PaymentStatus.failed)
    .group_by(Payment.order_id)
    .having(func.count(Payment.id) > 3)
    .all()
)
```

Rule: `filter()` = WHERE (before aggregation). `having()` = HAVING (after aggregation).

---

## JOINs

```python
# implicit join through filter (works when FK relationship exists)
self.db.query(Order, Payment).filter(Order.id == Payment.order_id).all()

# explicit join
self.db.query(Order).join(Payment, Order.id == Payment.order_id).all()

# LEFT OUTER JOIN — includes rows with no match on the right side
self.db.query(Order).outerjoin(Payment, Order.id == Payment.order_id).all()

# joining through ORM relationship (cleaner when relationship is defined on the model)
self.db.query(Order).join(Order.line_items).filter(OrderLineItem.product_id == product_id).all()
```

When to use each:
- `join()` → INNER JOIN — only rows that have a match on both sides
- `outerjoin()` → LEFT OUTER JOIN — all rows from left, NULLs where right has no match

---

## Subqueries

A subquery is a query used inside another query.

```python
# scalar subquery — returns a single value
from sqlalchemy import select

avg_spend = (
    select(func.avg(User.total_spent))
    .scalar_subquery()
)

# use in a filter: customers spending above average
high_spenders = (
    self.db.query(User)
    .filter(User.total_spent > avg_spend)
    .all()
)
```

```python
# .subquery() — returns a table-like object you can join against
from sqlalchemy import select

order_counts = (
    select(
        Order.user_id,
        func.count(Order.id).label("order_count"),
    )
    .group_by(Order.user_id)
    .subquery()
)

# join users against the subquery
results = (
    self.db.query(User, order_counts.c.order_count)
    .join(order_counts, User.id == order_counts.c.user_id)
    .all()
)
```

`.c` is how you access columns on a subquery (short for `.columns`).

---

## CTE — Common Table Expressions (WITH ... AS)

A CTE is a named subquery. In SQL:
```sql
WITH monthly_revenue AS (
    SELECT date_trunc('month', created_at) AS month, SUM(final_amount) AS revenue
    FROM orders WHERE status = 'completed'
    GROUP BY 1
)
SELECT * FROM monthly_revenue WHERE revenue > 10000;
```

In SQLAlchemy Core:
```python
from sqlalchemy import select, func

# define the CTE
monthly_revenue = (
    select(
        func.date_trunc("month", Order.created_at).label("month"),
        func.sum(Order.final_amount).label("revenue"),
    )
    .where(Order.status == OrderStatus.completed)
    .group_by(func.date_trunc("month", Order.created_at))
    .cte("monthly_revenue")  # .cte() gives it a name
)

# query the CTE like a table
results = self.db.execute(
    select(monthly_revenue).where(monthly_revenue.c.revenue > 10000)
).all()
```

### Multiple CTEs chained

```python
# WITH cte1 AS (...), cte2 AS (...) SELECT ...
cte1 = (
    select(Order.user_id, func.sum(Order.final_amount).label("total"))
    .group_by(Order.user_id)
    .cte("user_totals")
)

cte2 = (
    select(cte1.c.user_id, cte1.c.total)
    .where(cte1.c.total > 1000)
    .cte("high_value_users")
)

results = self.db.execute(
    select(User).join(cte2, User.id == cte2.c.user_id)
).scalars().all()
```

---

## Window Functions — ROW_NUMBER, LAG, LEAD, RANK

Window functions compute a value across a set of rows related to the current row,
without collapsing them into a GROUP BY result.

```python
from sqlalchemy import func
from sqlalchemy.sql import over

# func.xxx().over(partition_by=..., order_by=...)
```

### ROW_NUMBER — rank within a partition

```python
# number each payment per order by created_at
row_num = func.row_number().over(
    partition_by=Payment.order_id,
    order_by=Payment.created_at
).label("attempt_number")

results = self.db.query(Payment, row_num).all()
# row.attempt_number = 1 for first attempt, 2 for second, etc.
```

### LAG — previous row's value

```python
# for each order: the previous order's final_amount (for the same user)
prev_amount = func.lag(Order.final_amount).over(
    partition_by=Order.user_id,
    order_by=Order.created_at
).label("prev_order_amount")

results = self.db.query(
    Order.id,
    Order.final_amount,
    prev_amount,
).all()
# prev_order_amount = NULL for first order, previous order's amount for the rest
```

### LEAD — next row's value

Same as LAG but looks forward:
```python
next_amount = func.lead(Order.final_amount).over(
    partition_by=Order.user_id,
    order_by=Order.created_at
).label("next_order_amount")
```

### ROWS PRECEDING / FOLLOWING — running totals

```python
from sqlalchemy import func
from sqlalchemy.sql.expression import text

# running total of revenue, ordered by day
# "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" = running sum
running_total = func.sum(Order.final_amount).over(
    order_by=Order.created_at,
    rows=(None, 0)   # None = UNBOUNDED PRECEDING, 0 = CURRENT ROW
).label("running_revenue")
```

`rows=(None, 0)` = "from the beginning up to and including the current row".
`rows=(-1, 1)` = "one row before and one row after the current row".

### RANK and DENSE_RANK

```python
# rank customers by total spend
rank = func.rank().over(order_by=User.total_spent.desc()).label("spend_rank")
dense_rank = func.dense_rank().over(order_by=User.total_spent.desc()).label("dense_rank")

# difference: RANK skips numbers after ties (1, 1, 3). DENSE_RANK does not (1, 1, 2).
```

---

## COALESCE — handle NULLs

`COALESCE(a, b, c)` returns the first non-NULL value.

```python
from sqlalchemy import func, case

# replace NULL with a default
actual_or_estimated = func.coalesce(
    Shipment.actual_delivery_date,
    Shipment.estimated_delivery_date
).label("delivery_date")

# coalesce with a literal fallback
name = func.coalesce(User.full_name, "Unknown").label("display_name")
```

---

## CASE — conditional expressions

SQL's `CASE WHEN ... THEN ... ELSE ... END` maps to `case()`:

```python
from sqlalchemy import case

# simple case
status_label = case(
    (Order.status == OrderStatus.pending, "Waiting"),
    (Order.status == OrderStatus.confirmed, "Confirmed"),
    else_="Other"
).label("status_label")

# conditional count (count only rows matching a condition)
cancelled_count = func.count(
    case((Order.status == OrderStatus.cancelled, Order.id), else_=None)
).label("cancelled_count")

# use in query
results = self.db.query(
    Order.user_id,
    func.count(Order.id).label("total"),
    cancelled_count,
).group_by(Order.user_id).all()
```

---

## Date functions

```python
from sqlalchemy import func
from datetime import date, timedelta

# truncate to day/month/year
func.date_trunc("day", Order.created_at)
func.date_trunc("month", Order.created_at)
func.date_trunc("year", Order.created_at)

# today / now
func.current_date()
func.now()

# date arithmetic — orders in the last 30 days
thirty_days_ago = date.today() - timedelta(days=30)
self.db.query(Order).filter(Order.created_at >= thirty_days_ago).all()

# PostgreSQL interval arithmetic (via text for intervals)
from sqlalchemy import text
self.db.query(Order).filter(
    Order.created_at >= func.now() - text("interval '30 days'")
).all()

# extract year, month, day from a timestamp
func.extract("year", Order.created_at)
func.extract("month", Order.created_at)
func.extract("dow", Order.created_at)  # day of week (0=Sunday)
```

---

## Raw SQL with text()

When a query is too complex for the SQLAlchemy API, use `text()`:

```python
from sqlalchemy import text

# simple raw query
results = self.db.execute(
    text("SELECT id, full_name FROM users WHERE status = :status"),
    {"status": "active"}
).all()

# complex raw query with CTE and window functions
results = self.db.execute(text("""
    WITH monthly_cohort AS (
        SELECT
            date_trunc('month', u.registration_date) AS cohort_month,
            u.id AS user_id
        FROM users u
    ),
    monthly_spend AS (
        SELECT
            u.id AS user_id,
            date_trunc('month', o.created_at) AS order_month,
            SUM(o.final_amount) AS spend
        FROM users u
        JOIN orders o ON o.user_id = u.id
        WHERE o.status = 'completed'
        GROUP BY u.id, date_trunc('month', o.created_at)
    )
    SELECT
        c.cohort_month,
        s.order_month,
        SUM(s.spend) AS revenue
    FROM monthly_cohort c
    JOIN monthly_spend s ON s.user_id = c.user_id
    GROUP BY c.cohort_month, s.order_month
    ORDER BY c.cohort_month, s.order_month
""")).all()

for row in results:
    print(row.cohort_month, row.order_month, row.revenue)
```

---

## SQL Injection — why it works and why bound params stop it

This is interview-level knowledge. Understand the mechanism, not just the rule.

### Why string interpolation is dangerous

When you write:
```python
email = request.json["email"]
self.db.execute(text(f"SELECT * FROM users WHERE email = '{email}'"))
```

Python constructs a single string and hands it to PostgreSQL. PostgreSQL receives:
```sql
SELECT * FROM users WHERE email = 'user@example.com'
```

PostgreSQL has NO IDEA that `user@example.com` was "data". To it, the entire thing is
one flat string it needs to parse as SQL. **It cannot distinguish intent from content.**

### The attack

An attacker sends this as their email:
```
' OR '1'='1
```

Your f-string produces:
```sql
SELECT * FROM users WHERE email = '' OR '1'='1'
```

`'1'='1'` is always true. This query returns **every row in the users table**.

A more destructive payload:
```
'; DROP TABLE users; --
```

Produces:
```sql
SELECT * FROM users WHERE email = ''; DROP TABLE users; --'
```

PostgreSQL sees **two statements**: a SELECT then a DROP TABLE.
The `--` comments out the trailing `'` so the syntax is valid.
Your entire users table is gone.

### Why this is possible: the parser sees one flat string

The root cause: PostgreSQL parses SQL as text. When the SQL and the data arrive
as one concatenated string, the parser has to decide on its own what is "code" and
what is "data". Anything that looks like SQL syntax gets treated as SQL syntax.

The attacker's goal is always the same: **escape from the data context back into the SQL context**.
A `'` closes the string literal. Once outside the string, they can inject any SQL they want.

### Why bound parameters fix it — the key insight

```python
self.db.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email}
)
```

With bound parameters, the SQL template and the data travel to PostgreSQL **separately**.

PostgreSQL processes them in two distinct steps:
1. **Parse the SQL template first** — at this point `:email` is a placeholder, not a value
2. **Bind the value** — the value is inserted AFTER parsing, treated as a raw opaque value

So if the attacker sends `' OR '1'='1`:
- Step 1: PostgreSQL parses `SELECT * FROM users WHERE email = $1` (it converts `:email` to `$1`)
- Step 2: PostgreSQL sets `$1 = "' OR '1'='1"` as a literal string value
- The query looks for a user whose email is literally the string `' OR '1'='1` — finds none, returns nothing

**The parser never sees the attacker's characters as SQL.** They arrive after parsing is complete.

### The edge case that still trips people up

Bound parameters only work for **values** (strings, numbers, dates in WHERE/INSERT/UPDATE).
They do NOT work for structural SQL elements like table names, column names, or ORDER BY.

```python
# This is still vulnerable — bound params don't work for column names
sort_col = request.query_params.get("sort_by")
self.db.execute(
    text(f"SELECT * FROM orders ORDER BY {sort_col}"),  # STILL an f-string
    {}
)
# attacker sends: sort_by = "id; DROP TABLE orders; --"
```

For dynamic column names, **whitelist**:
```python
ALLOWED_SORT_COLUMNS = {"created_at", "final_amount", "status"}
if sort_col not in ALLOWED_SORT_COLUMNS:
    raise ValueError(f"Invalid sort column: {sort_col}")
self.db.execute(text(f"SELECT * FROM orders ORDER BY {sort_col}"), {})
# safe — sort_col is guaranteed to be one of three known column names
```

The whitelist works because you're checking against a hardcoded set of known-safe values
before the string concatenation happens. The attacker can't inject what's not on the list.

### Summary

| Approach | Safe? | Why |
|---|---|---|
| f-string with user input | No | SQL and data parsed together, attacker can escape string context |
| Bound params (`:name`) | Yes for values | SQL parsed before data is bound — parser never sees attacker's chars |
| Bound params for column names | No | Column names are structural — PostgreSQL can't parameterise them |
| Whitelist + f-string for column names | Yes | Only hardcoded safe values ever reach the SQL string |

---

## Switching from session.query() to Core select()

These are two different query APIs in SQLAlchemy. You need to understand both
because `session.query()` cannot express CTEs or window functions.

### What session.query() is

`session.query()` is SQLAlchemy's original ORM query interface (1.x era).
It's designed around ORM model classes. It implicitly knows about relationships,
columns, and how to map results back to Python objects.

```python
# returns a list of User ORM objects — relationships work, model_validate works
users = self.db.query(User).filter(User.status == "active").all()
```

The result is directly a `list[User]`. SQLAlchemy handles all the mapping for you.

### What select() is

`select()` is SQLAlchemy Core — a lower-level, SQL-like API. It builds a SELECT
statement as a composable object. It's what `session.query()` compiles down to internally.
Required for CTEs and window functions because those are SQL constructs that the ORM
query interface can't model.

```python
from sqlalchemy import select

stmt = select(User).where(User.status == "active")
users = self.db.execute(stmt).scalars().all()
```

Same result as above — but the path is different.

### Why session.query() can't do CTEs

A CTE produces a named, queryable result set. To query a CTE you need to treat it
like a table — join against it, select columns from it. `session.query()` only knows
about ORM model classes, not arbitrary named result sets.

```python
# This is NOT possible with session.query() — no way to hand it a CTE as a "table"
cte = select(Order.user_id, func.sum(Order.final_amount).label("total")).cte("totals")
self.db.query(cte).all()   # TypeError — query() doesn't accept a CTE

# Core select() works because CTEs are just SQL objects it understands
self.db.execute(select(cte).where(cte.c.total > 1000)).all()  # works
```

### The .scalars() vs .all() distinction

`session.execute()` always returns a `Result` object (a cursor-like thing).
How you extract rows from it depends on what you queried:

```python
# select on a full model → returns rows each containing one ORM object
# .scalars() unwraps each row to just the object, .all() collects them
users = self.db.execute(select(User)).scalars().all()
# → list[User]

# select on specific columns → returns rows as named tuples
rows = self.db.execute(
    select(User.id, User.email, func.count(Order.id).label("order_count"))
    .join(Order, User.id == Order.user_id)
    .group_by(User.id, User.email)
).all()
# → list[Row]  — access as row.id, row.email, row.order_count

# .scalar() (singular) → single value from a single-column single-row result
count = self.db.execute(select(func.count(User.id))).scalar()
# → int
```

Rule:
- Full model select → `.scalars().all()` to get ORM objects
- Multi-column / aggregate select → `.all()` to get named `Row` tuples
- Single value → `.scalar()`

### Side-by-side comparison

```python
# same query, two styles

# session.query() — ORM style
users = (
    self.db.query(User)
    .filter(User.status == "active")
    .order_by(User.registration_date.desc())
    .limit(10)
    .all()
)

# select() — Core style
users = self.db.execute(
    select(User)
    .where(User.status == "active")
    .order_by(User.registration_date.desc())
    .limit(10)
).scalars().all()

# both return list[User], both generate identical SQL
```

For simple ORM queries: `session.query()` is more concise.
For anything involving CTEs, window functions, or complex aggregates: `select()`.
For the most complex analytics: `text()`.

---

## Which API to use — decision table

| Query type | Use |
|---|---|
| Single row by ID | `session.query(Model).filter().first()` |
| List with simple filters | `session.query(Model).filter().all()` |
| Aggregates without GROUP BY | `session.query(func.count(...)).scalar()` |
| GROUP BY + aggregates | `session.query(func.x, ...).group_by().all()` |
| CTE | `select().cte()` + `session.execute()` |
| Window functions | `func.xxx().over(...)` inside `select()` + `session.execute()` |
| Multi-CTE, cohort analysis | `text()` with bound params |

---

## Can I just use text() everywhere if I know SQL?

Yes — and for complex analytics queries it's often the right call.
But the tradeoff depends on which layer you're in.

### For CRUD methods — don't use text()

```python
# ORM — 2 lines, relationship auto-loaded
order = (
    self.db.query(Order)
    .options(selectinload(Order.line_items))
    .filter(Order.id == order_id)
    .first()
)

# text() — you get a raw Row, no .line_items, no model_validate
result = self.db.execute(
    text("SELECT * FROM orders WHERE id = :id"), {"id": str(order_id)}
).one_or_none()
# now you have to manually JOIN line_items and map columns to Pydantic yourself
```

What you lose with `text()` in CRUD:
- **Relationship loading** — `selectinload`/`joinedload` don't work; you have to JOIN manually
- **`model_validate(orm)`** — you get raw `Row` tuples, not ORM objects
- **Rename safety** — if a DB column is renamed, `text()` queries silently break at runtime

### For analytics queries — use text() freely

```python
def get_order_lifecycle(self, order_id: UUID) -> dict:
    result = self.db.execute(text("""
        SELECT
            o.created_at            AS order_created,
            p.processed_at          AS payment_completed,
            s.updated_at            AS dispatched_at,
            s.actual_delivery_date  AS delivered_at
        FROM orders o
        LEFT JOIN payments p  ON p.order_id = o.id AND p.status = 'completed'
        LEFT JOIN shipments s ON s.order_id = o.id
        WHERE o.id = :order_id
    """), {"order_id": str(order_id)}).one_or_none()
```

Analytics queries are never mapping to ORM objects anyway — they return dicts or
custom Pydantic response shapes. Plain SQL is cleaner here than the equivalent
SQLAlchemy Core expression, especially for CTEs, window functions, and date bucketing.

### The rule

| Layer | Use |
|---|---|
| CRUD (create, get, update, delete) | ORM `session.query()` — relationships, type safety |
| Simple aggregates in repos | `session.query(func.count(...))` — still ORM, just with `func` |
| Analytics service (Q1–Q20) | `text()` — you know SQL, just write SQL |

### The one hard rule with text() — bound parameters

Never interpolate values into the SQL string. Always use bound params:

```python
# GOOD — bound param, safe
self.db.execute(
    text("SELECT * FROM orders WHERE user_id = :uid"),
    {"uid": str(user_id)}
)

# BAD — SQL injection vulnerability, even for internal APIs
self.db.execute(text(f"SELECT * FROM orders WHERE user_id = '{user_id}'"))
```
