import uuid
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Text, Date, ForeignKey, Index, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as PG_TIMESTAMP
from sqlalchemy.sql import func
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.orders import Order


class Shipment(Base):
    __tablename__ = "shipments"

    __table_args__ = (
        # tracking number must be unique per carrier, but can be null until dispatched
        UniqueConstraint("carrier", "tracking_number", name="uq_shipments_carrier_tracking"),
        Index("ix_shipments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True         # one shipment per order — enforced at DB level
    )
    carrier: Mapped[str] = mapped_column(String(30), nullable=False)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="preparing")
    estimated_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    shipping_address: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(PG_TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        PG_TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["Order"] = relationship("Order", back_populates="shipment")
