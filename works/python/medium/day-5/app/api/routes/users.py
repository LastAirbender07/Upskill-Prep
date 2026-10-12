from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError
from app.services.users import UsersService
from app.schemas.users import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserProfileResponse,
    SuspendRequest,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    try:
        return UsersService(db).create_user(data)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/", response_model=list[UserResponse])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return UsersService(db).list_users(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    try:
        return UsersService(db).get_user(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def get_customer_profile(user_id: UUID, db: Session = Depends(get_db)):
    try:
        return UsersService(db).get_customer_profile(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: UUID, data: UserUpdate, db: Session = Depends(get_db)):
    try:
        return UsersService(db).update_user(user_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{user_id}/suspend", response_model=UserResponse)
def suspend_user(user_id: UUID, body: SuspendRequest, db: Session = Depends(get_db)):
    try:
        return UsersService(db).suspend_user(user_id, body.reason)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    try:
        UsersService(db).delete_user(user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
