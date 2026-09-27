from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.users import User
from app.schemas.users import UserCreate, UserUpdate, UserResponse
from app.core.logger import get_logger

logger = get_logger(__name__)


class UsersRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user: UserCreate) -> UserResponse:
        # model_dump() converts Pydantic object → plain dict
        # ** unpacks that dict as keyword arguments into the ORM constructor
        user_orm = User(**user.model_dump())

        self.db.add(user_orm)

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.exception("Failed to create user due to integrity error")
            raise ValueError("User creation failed due to integrity error") from e

        # refresh pulls the DB-generated values back into the ORM object
        # (id, registration_date, status — anything set by server_default)
        self.db.refresh(user_orm)

        logger.info(f"Created user {user_orm.id}")

        # model_validate converts ORM object → Pydantic response
        # works because UserResponse has model_config = ConfigDict(from_attributes=True)
        return UserResponse.model_validate(user_orm)

    def get_by_id(self, user_id) -> UserResponse | None:
        user_orm = self.db.query(User).filter(User.id == user_id).first()

        if user_orm is None:
            return None

        return UserResponse.model_validate(user_orm)

    def get_by_email(self, email: str) -> UserResponse | None:
        user_orm = self.db.query(User).filter(User.email == email).first()

        if user_orm is None:
            return None

        return UserResponse.model_validate(user_orm)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[UserResponse]:
        users = self.db.query(User).offset(skip).limit(limit).all()
        return [UserResponse.model_validate(user) for user in users]

    def update_user(self, user_id, update_data: UserUpdate) -> UserResponse | None:
        user_orm = self.db.query(User).filter(User.id == user_id).first()

        if user_orm is None:
            return None

        # exclude_unset=True means only fields the caller actually provided are updated
        # if caller sends {"full_name": "John"}, phone_number is NOT touched
        update_dict = update_data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            setattr(user_orm, field, value)

        self.db.commit()
        self.db.refresh(user_orm)

        return UserResponse.model_validate(user_orm)

    def delete_user(self, user_id) -> bool:
        user_orm = self.db.query(User).filter(User.id == user_id).first()

        if user_orm is None:
            return False

        try:
            self.db.delete(user_orm)
            self.db.commit()
            return True
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError("Cannot delete user with existing orders") from e
