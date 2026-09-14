# Event Commerce Platform — Business Requirements

## Context

You are building the backend for a small e-commerce platform. The platform processes orders, payments,
and shipments. Your job is to model this domain properly, expose business logic through a service layer,
and learn PostgreSQL through real query problems — not textbook exercises.

---

## Domain Entities

### 1. Customer

Represents a registered user of the platform.

**Fields:**
- Unique ID
- Full name
- Email address (must be unique across the system)
- Phone number (optional)
- Account status: `active`, `suspended`, `closed`
- Registration date
- Last login date (nullable)
- Total lifetime spend (denormalized — updated when orders complete)

**Business rules:**
- Email cannot be changed once registered
- A suspended customer cannot place new orders
- Lifetime spend must always reflect completed (paid) orders only

---

### 2. Product

Represents an item available for purchase.

**Fields:**
- Unique ID
- SKU (Stock Keeping Unit — unique, human-readable, e.g. `SHOE-RED-42`)
- Name
- Category (e.g. `electronics`, `clothing`, `food`)
- Price (base price in cents — avoid float precision problems)
- Stock quantity
- Status: `available`, `out_of_stock`, `discontinued`
- Created at

**Business rules:**
- Price is always stored in cents (integer), converted to decimal at the API layer
- A discontinued product cannot be added to new orders
- Stock quantity must never go negative

---

### 3. Order

Represents a customer's purchase intent.

**Fields:**
- Unique ID
- Customer ID (reference)
- Status: `pending`, `confirmed`, `processing`, `shipped`, `delivered`, `cancelled`, `refunded`
- Total amount (in cents)
- Discount amount (in cents, default 0)
- Final amount (total - discount)
- Created at
- Updated at
- Notes (optional free text)

**Business rules:**
- An order can only be cancelled if status is `pending` or `confirmed`
- Once `shipped`, an order cannot change status except to `delivered` or `refunded`
- Total amount must equal the sum of all its order line items
- A single customer must not have more than 5 `pending` orders at the same time

---

### 4. Order Line Item

Represents one product within an order.

**Fields:**
- Unique ID
- Order ID (reference)
- Product ID (reference)
- Quantity
- Unit price at time of purchase (snapshot — price can change later)
- Subtotal (quantity × unit price)

**Business rules:**
- Unit price is captured at order creation time, not looked up later
- Quantity must be at least 1
- You cannot add the same product twice to the same order; instead, update quantity
- Deleting a line item should recalculate the order total

---

### 5. Payment

Represents a payment attempt for an order.

**Fields:**
- Unique ID
- Order ID (reference)
- Amount (in cents)
- Status: `pending`, `processing`, `completed`, `failed`, `refunded`
- Payment method: `card`, `bank_transfer`, `wallet`
- Transaction reference (external ID from payment gateway — nullable until processed)
- Failure reason (nullable — only set when status is `failed`)
- Created at
- Processed at (nullable)

**Business rules:**
- An order can have multiple payment attempts (first attempt fails, retry succeeds)
- Only one payment per order can be in `completed` state at a time
- A `refunded` payment must have a corresponding record of the refund amount
- Payment amount must match the order's final amount exactly
- A payment cannot be retried if the order is `cancelled`

---

### 6. Shipment

Represents physical delivery of a confirmed, paid order.

**Fields:**
- Unique ID
- Order ID (reference — one-to-one)
- Carrier: `fedex`, `ups`, `dhl`, `local_courier`
- Tracking number (nullable until dispatched)
- Status: `preparing`, `dispatched`, `in_transit`, `delivered`, `returned`
- Estimated delivery date
- Actual delivery date (nullable)
- Shipping address (snapshot — copy of customer address at time of shipment)
- Created at
- Updated at

**Business rules:**
- A shipment is only created after a payment is `completed`
- An order can have at most one shipment
- Once `delivered`, a shipment status cannot change
- Tracking number must be unique per carrier

---

### 7. Event Log

Represents a domain event that occurred in the system. Used for audit trail and eventually Kafka.

**Fields:**
- Unique ID
- Event type: `order_created`, `order_cancelled`, `payment_completed`, `payment_failed`, `shipment_dispatched`, `customer_suspended`, etc.
- Aggregate type: `order`, `payment`, `customer`, `shipment`
- Aggregate ID (the ID of the affected entity)
- Payload (JSON — full snapshot of the event data)
- Occurred at

**Business rules:**
- Events are append-only — never updated or deleted
- Every significant state change (see above types) must produce an event log entry
- The payload must contain enough data to reconstruct what happened without joining other tables

---

## Query Requirements

These are the real analytical queries you must be able to answer. Design your schema to make these
efficient, not just correct.

### Customer queries

| # | Question |
|---|----------|
| Q1 | Top 10 customers by lifetime spend |
| Q2 | Customers who registered in the last 30 days but have never placed an order |
| Q3 | Customers with more than 3 failed payments in their history |
| Q4 | Customers whose monthly spend increased by more than 30% compared to the previous month |

### Order queries

| # | Question |
|---|----------|
| Q5 | Daily order count and revenue for the past 90 days |
| Q6 | Orders that have been in `processing` status for more than 48 hours |
| Q7 | Average order value broken down by product category |
| Q8 | Orders where the customer was suspended after placing the order |

### Payment queries

| # | Question |
|---|----------|
| Q9 | All failed payments in the last 24 hours with their failure reasons |
| Q10 | Payment success rate per day (completed / total attempts) for the last 30 days |
| Q11 | Orders that have had more than 2 payment attempts |
| Q12 | Total revenue collected per payment method per month |

### Shipment queries

| # | Question |
|---|----------|
| Q13 | Shipments that are overdue (past estimated delivery date, not yet delivered) |
| Q14 | Average actual delivery time (days) by carrier for the last 60 days |
| Q15 | Orders that were paid but have no shipment created yet |

### Cross-entity / complex queries

| # | Question |
|---|----------|
| Q16 | For each customer: their order count, total spent, last order date, and most purchased category |
| Q17 | Products that appear most often in cancelled orders (signals pricing or availability problems) |
| Q18 | The full lifecycle of an order: created → paid → dispatched → delivered with timestamps |
| Q19 | Customers who placed an order but whose payment failed and have not retried in 7+ days |
| Q20 | Daily revenue cohort: revenue from customers who joined in month X, tracked each subsequent month |

---

## Indexing Requirements

Think carefully about which columns to index. You should be able to justify each index with a specific query.

The following access patterns happen at high frequency:

- Look up orders by customer ID
- Look up payments by order ID
- Filter orders by status
- Filter payments by status
- Filter shipments by status
- Look up events by aggregate type + aggregate ID
- Sort orders and payments by created_at

Some access patterns are less frequent but expensive:

- Analytical queries aggregating by date ranges
- Cross-table joins between orders, payments, and customers

You will need to:
- Decide which of the above need a single-column index
- Decide which need a composite index (and in what order)
- Use `EXPLAIN ANALYZE` to verify your assumptions
- Learn when an index makes things worse (writes, small tables)

---

## Service Layer Functions

These are the business operations your service layer must support. Each one implies a function with
specific validation, transaction management, and side effects.

### Customer Service
- `create_customer(data)` — validate uniqueness, set defaults
- `suspend_customer(customer_id, reason)` — status change + event log
- `get_customer_profile(customer_id)` — customer + their order summary stats
- `get_top_customers(limit, period_days)` — analytical query

### Order Service
- `create_order(customer_id, items)` — validate customer status, check stock, snapshot prices, calculate total
- `add_item_to_order(order_id, product_id, quantity)` — validate order status, update total
- `cancel_order(order_id)` — validate state machine, restore stock, log event
- `get_order_details(order_id)` — order + line items + payment + shipment
- `get_orders_by_customer(customer_id, filters)` — paginated list with filtering by status

### Payment Service
- `initiate_payment(order_id, method)` — validate no existing completed payment, create pending record
- `confirm_payment(payment_id, transaction_ref)` — mark completed, trigger order status change, log event
- `fail_payment(payment_id, reason)` — mark failed, log event
- `get_payment_history(order_id)` — all attempts for an order

### Shipment Service
- `create_shipment(order_id, carrier, estimated_date, address)` — validate payment complete, create record
- `dispatch_shipment(shipment_id, tracking_number)` — validate state, set tracking, log event
- `mark_delivered(shipment_id, actual_date)` — terminal state, log event, update order status

### Analytics Service (the interesting PostgreSQL work)
- `get_daily_revenue(start_date, end_date)` — Q5
- `get_overdue_shipments()` — Q13
- `get_customer_spending_trend(customer_id)` — month-over-month breakdown
- `get_payment_failure_summary(hours=24)` — Q9
- `get_order_lifecycle(order_id)` — Q18

---

## State Machines

These must be enforced at the service layer — not just the database.

**Order status transitions (allowed only):**
```
pending → confirmed → processing → shipped → delivered
pending → cancelled
confirmed → cancelled
shipped → refunded
delivered → refunded
```

**Payment status transitions:**
```
pending → processing → completed
pending → processing → failed
failed → pending  (retry path)
completed → refunded
```

**Shipment status transitions:**
```
preparing → dispatched → in_transit → delivered
in_transit → returned
```

---

## Data Volume Expectations (for indexing/query design decisions)

- Customers: ~500,000 records
- Products: ~10,000 records
- Orders: ~5,000,000 records
- Order line items: ~15,000,000 records
- Payments: ~6,000,000 records
- Shipments: ~4,000,000 records
- Event logs: ~30,000,000 records

These numbers are the reason EXPLAIN ANALYZE will matter. A query that works on 100 rows will fail on 5 million.

---

## Migration Requirements (Alembic)

You should version every schema change. Specific things to practice:

- Initial table creation (baseline migration)
- Adding a non-nullable column to an existing table (requires a default or backfill strategy)
- Adding an index after the fact (simulate discovering a slow query)
- Adding a foreign key constraint to an existing table
- Renaming a column without data loss

---

## What You Are NOT Building

Keep scope tight. These are explicitly out of scope:

- Authentication / JWT / sessions
- Email / notifications
- Admin UI
- Actual payment gateway integration (mock it)
- Multi-currency (everything is in cents, single currency)
- Multi-warehouse / inventory locations
