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
