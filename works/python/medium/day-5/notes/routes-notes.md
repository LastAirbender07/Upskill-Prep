# Route Layer Notes

## What the route layer is

The route layer sits at the top of the stack. Its only job is HTTP: parse the request,
call the service, translate the result back to HTTP.

```
HTTP request
   ↓
Route    — parse input, call service, map errors to HTTP status codes
   ↓
Service  — business logic
   ↓
CRUD     — DB reads/writes
   ↓
PostgreSQL
```

**The route layer knows about HTTP. The service layer does not.**

Route asks: "What status code do I return? What's in the response body?"
Service asks: "Is this operation allowed given the current state of the system?"

If you see `HTTPException` in a service — move it to the route.
If you see business conditions (`user.status == "active"`) in a route — move it to the service.

---

## APIRouter — organising routes by entity

Instead of registering every route directly on `app`, group related routes in an `APIRouter`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/{user_id}")
def get_user(...): ...
```

- `prefix` — prepended to every route in this router (`/users/{user_id}`)
- `tags` — groups routes under a label in the auto-generated `/docs` (Swagger UI)

### Nesting routers in main.py

```python
# main.py
api_router = APIRouter(prefix="/v1")       # top-level versioned router
api_router.include_router(users_router)    # nest /users under /v1
api_router.include_router(orders_router)   # nest /orders under /v1
app.include_router(api_router)             # mount /v1 on the app

# final URLs: /v1/users/, /v1/users/{id}, /v1/orders/, etc.
```

Add each new router to `main.py` in the same pattern — one line per entity.

---

## Dependency injection — Depends(get_db)

FastAPI's `Depends()` runs a function and injects its return value into the route:

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database.database import get_db

@router.get("/{user_id}")
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    ...
```

`get_db` is a generator that yields a session and closes it when the request ends:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db        # FastAPI injects this value into the route
    finally:
        db.close()      # runs after the route returns, even on errors
```

One session per request. The session is created when the request starts, closed when it ends.
Every route that touches the DB declares `db: Session = Depends(get_db)`.

---

## Path parameters, query parameters, and request body

FastAPI infers the type from the function signature — no decorators needed:

```python
@router.get("/{user_id}")                        # {user_id} in path → path param
def get_user(
    user_id: UUID,                               # matches {user_id} in path → path param
    include_deleted: bool = False,               # not in path, has default → query param
    db: Session = Depends(get_db),               # Depends → injected, not from request
):
```

```python
@router.post("/")
def create_user(
    data: UserCreate,                            # Pydantic model → request body (JSON)
    db: Session = Depends(get_db),
):
```

```python
@router.get("/")
def list_users(
    skip: int = 0,                               # query param: /users/?skip=0&limit=20
    limit: int = 100,
    db: Session = Depends(get_db),
):
```

Rule:
- Path → must appear in the decorator path string as `{name}`
- Body → a Pydantic `BaseModel` subclass (no default value)
- Query → any other typed param with a default value
- Injected → `Depends(...)`

---

## response_model and status_code

```python
@router.post("/", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    return UsersService(db).create_user(data)
```

- `response_model` — FastAPI serializes the return value using this Pydantic schema.
  Extra fields on the ORM object are stripped. Missing fields raise a validation error.
  Always set this — it's the contract your API promises to callers.

- `status_code` — the HTTP status code on success. Default is 200 if omitted.
  Use `status.HTTP_201_CREATED` instead of the raw int — it's self-documenting.

### Common status codes

| Code | Constant | When |
|---|---|---|
| 200 | `HTTP_200_OK` | Successful read or update |
| 201 | `HTTP_201_CREATED` | Resource successfully created |
| 204 | `HTTP_204_NO_CONTENT` | Success but nothing to return (DELETE) |
| 400 | `HTTP_400_BAD_REQUEST` | Malformed request syntax |
| 404 | `HTTP_404_NOT_FOUND` | Resource does not exist |
| 409 | `HTTP_409_CONFLICT` | Request valid but conflicts with current state (duplicate email) |
| 422 | `HTTP_422_UNPROCESSABLE_ENTITY` | Request understood but business rule violated |
| 500 | `HTTP_500_INTERNAL_SERVER_ERROR` | Unexpected server error |

Note: FastAPI automatically returns 422 when Pydantic validation fails on the request body —
you don't need to handle that manually.

---

## HTTP verbs — when to use GET, POST, PUT, PATCH, DELETE

### The quick reference

| Verb | Use for | Idempotent? | Has body? |
|---|---|---|---|
| `GET` | Read a resource or list | Yes | No |
| `POST` | Create a new resource, or trigger an action | No | Yes |
| `PUT` | Replace a resource completely | Yes | Yes |
| `PATCH` | Update specific fields of a resource | No* | Yes |
| `DELETE` | Remove a resource | Yes | No |

*Idempotent = calling it twice with the same input produces the same result.

---

### GET — read only, no side effects

```python
@router.get("/", response_model=list[ProductResponse])       # list
@router.get("/{product_id}", response_model=ProductResponse) # single
```

Never use GET for writes. No request body.

---

### POST — create, or trigger an action

**Create a new resource:**
```python
@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, ...):
```
The resource doesn't exist yet — POST brings it into existence. Returns 201.

**Trigger an action (command endpoint):**
```python
@router.post("/{product_id}/restock", response_model=ProductResponse)
def restock_product(product_id: UUID, body: RestockRequest, ...):
```
Used when the operation is a meaningful business action with side effects, not a simple field change:
- The input is a delta (`quantity: 50` = "add 50"), not a target value
- There's business logic (check discontinued, potentially flip status)
- Calling it twice with the same input changes state twice (not idempotent)

Pattern: `POST /{resource}/{id}/action`

---

### PUT — full replacement (rarely used in practice)

```python
@router.put("/{product_id}", response_model=ProductResponse)
def replace_product(product_id: UUID, data: ProductReplace, ...):
```

PUT means: "take everything I'm sending and replace the entire resource with it."
If the product has 10 fields and you PUT with 2 fields, the other 8 become null or default.

The service for a PUT must NOT use `exclude_unset=True` — every field must be present.

**When to use it:** rarely. Only if the caller always sends the complete object (e.g. a config file upload, overwriting a settings document). Most update endpoints are PATCH.

**The tell:** if your schema has `Optional` fields, it's PATCH, not PUT.

---

### PATCH — partial update (most common update verb)

```python
@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(product_id: UUID, data: ProductUpdate, ...):
```

PATCH means: "update only the fields I'm sending, leave everything else unchanged."

The service uses `model_dump(exclude_unset=True)` so only fields explicitly sent in the request body get written to the DB.

```python
# PATCH /products/{id} with body {"name": "New Name"}
# → only name is updated, price/sku/category are untouched
```

**PATCH for state transitions** is also common:
```python
@router.patch("/{product_id}/discontinue", response_model=ProductResponse)
def discontinue_product(product_id: UUID, ...):
```
There's no body needed — the action IS the transition. `/discontinue` reads like "apply this
partial change (status = discontinued) to the resource."

**The rule:**
- Schema has Optional fields + service uses `exclude_unset=True` → `PATCH`
- Meaningful business action with side effects, additive/delta input → `POST /action`
- Full replacement → `PUT`

---

### DELETE — remove a resource

```python
@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: UUID, ...):
```

Returns 204 (no body). Idempotent — deleting something that's already gone should return 404,
not an error that breaks the caller.

---

### Summary: how this project uses each verb

| Endpoint | Verb | Why |
|---|---|---|
| `POST /users/` | POST | Creating a new user |
| `GET /users/{id}` | GET | Reading a user |
| `PATCH /users/{id}` | PATCH | Partial field update |
| `POST /users/{id}/suspend` | POST | Business action with side effects (log event) |
| `DELETE /users/{id}` | DELETE | Remove resource |
| `PATCH /products/{id}` | PATCH | Partial field update (name, price, etc.) |
| `PATCH /products/{id}/discontinue` | PATCH | State transition (no body needed) |
| `POST /products/{id}/restock` | POST | Additive action, side effects, not idempotent |

### 204 — no return value

```python
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    UsersService(db).delete_user(user_id)
    # no return statement — FastAPI sends an empty body, which is correct for 204
```

If you set `status_code=204` and return something, FastAPI will strip it. Leave the return implicit.

---

## ValueError → HTTPException — the error translation pattern

The service raises `ValueError` for all business errors.
The route's job is to translate those into the right HTTP status code.

```python
from fastapi import HTTPException, status

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    try:
        return UsersService(db).get_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

`HTTPException` is how you tell FastAPI "return this status code with this message":
```json
{"detail": "User abc-123 not found"}
```

### Mapping rules

| Service raises | Route returns |
|---|---|
| `"... not found"` | 404 — the resource doesn't exist |
| `"... already exists"` | 409 — conflicts with existing state |
| `"Cannot suspend a closed account"` | 422 — valid request, but business rule says no |

### When one route can raise multiple different codes

Some operations can fail in multiple distinct ways. With typed exception classes you catch by
type — no message parsing needed:

```python
# app/exceptions.py
class NotFoundError(ValueError):    # → 404
class ConflictError(ValueError):    # → 409
class BusinessRuleError(ValueError):  # → 422

# suspend_user raises NotFoundError OR BusinessRuleError depending on which guard fires
@router.post("/{user_id}/suspend", response_model=UserResponse)
def suspend_user(user_id: UUID, body: SuspendRequest, db: Session = Depends(get_db)):
    try:
        return UsersService(db).suspend_user(user_id, body.reason)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
```

The route catches different types in separate `except` blocks — each maps to exactly one status code.
No string inspection. If the service adds a new guard it just raises the right typed exception,
and the route handles it correctly without any change.

---

## def vs async def

```python
# sync — what we use
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    return service.get_user(user_id)

# async — for async DB drivers (asyncpg, databases, etc.)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_async_db)):
    return await service.get_user(user_id)
```

We use SQLAlchemy's synchronous ORM (`Session`, not `AsyncSession`), so regular `def` is correct.
Using `async def` with a synchronous DB driver doesn't give you any benefit — the DB call still blocks.

FastAPI runs sync routes in a thread pool automatically, so they don't block the event loop.

---

## Route-specific request schemas

Not every operation maps to a CRUD schema. Sometimes a route needs a small, purpose-specific body.

```python
# schemas/users.py
class SuspendRequest(BaseModel):
    reason: str
```

The route unpacks it and passes only what the service needs:
```python
def suspend_user(user_id: UUID, body: SuspendRequest, db: ...):
    service.suspend_user(user_id, body.reason)   # service only sees a plain str
```

The service never knows about `SuspendRequest`. The schema is a route-layer concern — it
defines the shape of one specific HTTP request body and nothing else.

---

## What the route layer does NOT do

- No business logic (`if user.status == "active"`) — that's the service's job
- No DB queries directly — always goes through the service
- No `ValueError` raises — only `HTTPException`
- No `try/except IntegrityError` — that's the CRUD layer's job

If you find yourself writing any of the above in a route — it belongs somewhere else.
