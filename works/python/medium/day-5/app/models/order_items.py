import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Numeric, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.orders import Order
    from app.models.products import Product


class OrderLineItem(Base):
    __tablename__ = "order_line_items"

    __table_args__ = (
        # enforces: same product cannot appear twice in the same order
        UniqueConstraint("order_id", "product_id", name="uq_order_line_items_order_product"),
        CheckConstraint("quantity >= 1", name="ck_order_line_items_quantity_positive"),
        CheckConstraint("unit_price > 0", name="ck_order_line_items_unit_price_positive"),
        Index("ix_order_line_items_order_id", "order_id"),
        Index("ix_order_line_items_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="line_items")
    product: Mapped["Product"] = relationship("Product", back_populates="line_items")
