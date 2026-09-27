import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Text, Numeric, ForeignKey, Index, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as PG_TIMESTAMP
from sqlalchemy.sql import func
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.orders import Order


class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    transaction_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(PG_TIMESTAMP(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(PG_TIMESTAMP(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payments")
