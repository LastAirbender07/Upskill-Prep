from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from app.models.orders import Order
from app.models.order_items import OrderLineItem
from app.models.products import Product
from app.schemas.orders import OrderCreateInternal, OrderResponse, OrderItemResponse
from app.schemas.enums import OrderStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_order(self, data: OrderCreateInternal) -> OrderResponse:
        # service layer has already validated the user, checked stock, and computed amounts
        # CRUD just writes what it is given
        order_orm = Order(
            user_id=data.user_id,
            total_amount=data.total_amount,
            discount_amount=data.discount_amount,
            final_amount=data.final_amount,
            notes=data.notes,
        )
        self.db.add(order_orm)
        self.db.flush()  # flush to get order_orm.id without committing yet

        # create line items using the order id
        for item in data.items:
            line_item = OrderLineItem(
                order_id=order_orm.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            self.db.add(line_item)

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.exception("Failed to create order due to integrity error")
            raise ValueError("Order creation failed due to integrity error") from e

        self.db.refresh(order_orm)
        logger.info(f"Created order {order_orm.id} for user {data.user_id}")
        return OrderResponse.model_validate(order_orm)

    def get_by_id(self, order_id: UUID) -> OrderResponse | None:
        order_orm = (
            self.db.query(Order)
            .options(
                selectinload(Order.line_items)
            )  # eager load line items in one extra query
            .filter(Order.id == order_id)
            .first()
        )

        if order_orm is None:
            return None

        return OrderResponse.model_validate(order_orm)

    def get_by_user(
        self,
        user_id: UUID,
        status: Optional[OrderStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[OrderResponse]:
        query = (
            self.db.query(Order)
            .options(selectinload(Order.line_items))
            .filter(Order.user_id == user_id)
        )

        if status is not None:
            query = query.filter(Order.status == status)

        orders = query.offset(skip).limit(limit).all()
        return [OrderResponse.model_validate(order) for order in orders]

    def get_pending_count_by_user(self, user_id: UUID) -> int:
        # used by service layer to enforce: max 5 pending orders per user
        return (
            self.db.query(Order)
            .filter(Order.user_id == user_id, Order.status == OrderStatus.pending)
            .count()
        )

    def update_status(
        self, order_id: UUID, new_status: OrderStatus
    ) -> OrderResponse | None:
        order_orm = self.db.query(Order).filter(Order.id == order_id).first()

        if order_orm is None:
            return None

        order_orm.status = new_status
        self.db.commit()
        self.db.refresh(order_orm)
        return OrderResponse.model_validate(order_orm)

    def update_amounts(
        self, order_id: UUID, total_amount: float, discount_amount: float, final_amount: float
    ) -> OrderResponse | None:
        # called when a line item is added or removed — recalculates totals
        order_orm = self.db.query(Order).filter(Order.id == order_id).first()

        if order_orm is None:
            return None

        order_orm.total_amount = total_amount
        order_orm.discount_amount = discount_amount
        order_orm.final_amount = final_amount
        self.db.commit()
        self.db.refresh(order_orm)
        return OrderResponse.model_validate(order_orm)

    def get_orm_by_id(self, order_id: UUID) -> Order | None:
        # returns the raw ORM object — used by service layer when it needs to mutate state
        return self.db.query(Order).filter(Order.id == order_id).first()
