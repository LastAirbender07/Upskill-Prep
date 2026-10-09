from uuid import UUID
from sqlalchemy.orm import Session
from app.crud.users_repository import UsersRepository
from app.schemas.users import UserCreate, UserResponse, UserUpdate
from app.schemas.enums import AccountStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class UsersService:
    def __init__(self, db: Session):
        self.repo = UsersRepository(db)

    def create_user(self, data: UserCreate) -> UserResponse:
        existing = self.repo.get_by_email(data.email)
        if existing:
            raise ValueError(f"A user with email '{data.email}' already exists")
        return self.repo.create_user(data)

    def get_user(self, user_id: UUID) -> UserResponse:
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        return user

    def list_users(self, skip: int = 0, limit: int = 100) -> list[UserResponse]:
        return self.repo.get_all(skip=skip, limit=limit)

    def update_user(self, user_id: UUID, data: UserUpdate) -> UserResponse:
        existing = self.repo.get_by_id(user_id)
        if existing is None:
            raise ValueError(f"User {user_id} not found")
        return self.repo.update_user(user_id, data)

    def suspend_user(self, user_id: UUID, reason: str) -> UserResponse:
        existing = self.repo.get_by_id(user_id)
        if existing is None:
            raise ValueError(f"User {user_id} not found")
        if existing.status == AccountStatus.suspended:
            raise ValueError(f"User {user_id} is already suspended")
        if existing.status == AccountStatus.closed:
            raise ValueError("Cannot suspend a closed account")

        # TODO: write event log entry when EventLogRepository is wired in
        updated = self.repo.update_status(user_id, AccountStatus.suspended)
        logger.info(f"User {user_id} suspended — reason: {reason}")
        return updated

    def delete_user(self, user_id: UUID) -> None:
        existing = self.repo.get_by_id(user_id)
        if existing is None:
            raise ValueError(f"User {user_id} not found")
        # CRUD raises ValueError if user has existing orders (RESTRICT FK)
        self.repo.delete_user(user_id)
