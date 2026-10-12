from uuid import UUID
from sqlalchemy.orm import Session
from app.crud.users_repository import UsersRepository
from app.crud.orders_repository import OrderRepository
from app.crud.event_logs_repository import EventLogRepository
from app.schemas.users import UserCreate, UserResponse, UserUpdate, UserProfileResponse, OrderSummary
from app.schemas.enums import AccountStatus, EventType, AggregateType
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError
from app.core.logger import get_logger

logger = get_logger(__name__)


class UsersService:
    def __init__(self, db: Session):
        self.repo = UsersRepository(db)
        self.order_repo = OrderRepository(db)
        self.event_repo = EventLogRepository(db)

    def create_user(self, data: UserCreate) -> UserResponse:
        existing = self.repo.get_by_email(data.email)
        if existing:
            raise ConflictError(f"A user with email '{data.email}' already exists")
        return self.repo.create_user(data)

    def get_user(self, user_id: UUID) -> UserResponse:
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    def get_customer_profile(self, user_id: UUID) -> UserProfileResponse:
        user = self.repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")

        summary = self.order_repo.get_order_summary_by_user(user_id)

        return UserProfileResponse(
            user=user,
            orders=OrderSummary(
                order_count=summary["order_count"],
                pending_count=summary["pending_count"],
                last_order_date=summary["last_order_date"],
            ),
        )

    def list_users(self, skip: int = 0, limit: int = 100) -> list[UserResponse]:
        return self.repo.get_all(skip=skip, limit=limit)

    def update_user(self, user_id: UUID, data: UserUpdate) -> UserResponse:
        existing = self.repo.get_by_id(user_id)
        if existing is None:
            raise NotFoundError(f"User {user_id} not found")
        return self.repo.update_user(user_id, data)

    def suspend_user(self, user_id: UUID, reason: str) -> UserResponse:
        existing = self.repo.get_by_id(user_id)
        if existing is None:
            raise NotFoundError(f"User {user_id} not found")
        if existing.status == AccountStatus.suspended:
            raise BusinessRuleError(f"User {user_id} is already suspended")
        if existing.status == AccountStatus.closed:
            raise BusinessRuleError("Cannot suspend a closed account")

        updated = self.repo.update_status(user_id, AccountStatus.suspended)

        self.event_repo.create_event(
            event_type=EventType.customer_suspended,
            aggregate_type=AggregateType.customer,
            aggregate_id=user_id,
            payload={"reason": reason},
        )

        logger.info(f"User {user_id} suspended — reason: {reason}")
        return updated

    def delete_user(self, user_id: UUID) -> None:
        existing = self.repo.get_by_id(user_id)
        if existing is None:
            raise NotFoundError(f"User {user_id} not found")
        self.repo.delete_user(user_id)
