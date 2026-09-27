import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Text, String, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as PG_TIMESTAMP
from sqlalchemy.sql import func
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.orders import Order


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_status", "status"),
        Index("ix_users_registration_date", "registration_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    registration_date: Mapped[datetime] = mapped_column(
        PG_TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_date: Mapped[Optional[datetime]] = mapped_column(
        PG_TIMESTAMP(timezone=True), nullable=True
    )
    total_spent: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )

    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
