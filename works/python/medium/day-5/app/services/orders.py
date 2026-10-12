from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session
from app.crud.orders_repository import OrderRepository
from app.crud.products_repository import ProductRepository
from app.crud.users_repository import UsersRepository
from app.crud.event_logs_repository import EventLogRepository
from app.crud.payments_repository import PaymentRepository
from app.crud.shipments_repository import ShipmentRepository
from app.schemas.orders import (
    OrderCreate,
    OrderCreateInternal,
    OrderItemCreate,
    OrderItemInternal,
    OrderResponse,
    OrderDetailResponse,
)
from app.schemas.enums import (
    OrderStatus,
    ProductStatus,
    AccountStatus,
    EventType,
    AggregateType,
)
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError
from app.core.logger import get_logger

logger = get_logger(__name__)

_VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.pending: {OrderStatus.confirmed, OrderStatus.cancelled},
    OrderStatus.confirmed: {OrderStatus.processing, OrderStatus.cancelled},
    OrderStatus.processing: {OrderStatus.shipped},
    OrderStatus.shipped: {OrderStatus.delivered, OrderStatus.refunded},
    OrderStatus.delivered: {OrderStatus.refunded},
    OrderStatus.cancelled: set(),  # terminal
    OrderStatus.refunded: set(),  # terminal
}


class OrderService:
    def __init__(self, db: Session):
        self.order_repo = OrderRepository(db)
        self.product_repo = ProductRepository(db)
        self.user_repo = UsersRepository(db)
        self.event_repo = EventLogRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.shipment_repo = ShipmentRepository(db)

    def create_order(self, data: OrderCreate) -> OrderResponse:
        user = self.user_repo.get_by_id(data.user_id)
        if user is None:
            raise NotFoundError(f"User {data.user_id} not found")
        if user.status != AccountStatus.active:
            raise BusinessRuleError(
                f"User {data.user_id} account is '{user.status.value}' — cannot place orders"
            )

        if self.order_repo.get_pending_count_by_user(data.user_id) >= 5:
            raise BusinessRuleError(
                f"User {data.user_id} has reached the maximum of 5 pending orders"
            )

        # validate items and snapshot prices — no writes yet
        data_internal = self._construct_order_internal(data)

        # deduct stock via flush() — committed atomically with the order below
        for item in data_internal.items:
            self.product_repo.deduct_stock(item.product_id, item.quantity)

        created = self.order_repo.create_order(data_internal)

        self.event_repo.create_event(
            event_type=EventType.order_created,
            aggregate_type=AggregateType.order,
            aggregate_id=created.id,
            payload={"user_id": str(data.user_id), "item_count": len(data.items)},
        )

        return created

    def get_order(self, order_id: UUID) -> OrderResponse:
        order = self.order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")
        return order

    def get_orders_by_user(self, user_id: UUID) -> list[OrderResponse]:
        return self.order_repo.get_by_user(user_id)

    def get_order_details(self, order_id: UUID) -> OrderDetailResponse:
        order = self.order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")

        payments = self.payment_repo.get_by_order(order_id)
        shipment = self.shipment_repo.get_by_order(order_id)

        return OrderDetailResponse(order=order, payments=payments, shipment=shipment)

    def update_order_items(
        self, order_id: UUID, items: list[OrderItemCreate]
    ) -> OrderResponse:
        order = self.order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")
        if order.status != OrderStatus.pending:
            raise BusinessRuleError(
                f"Can only modify items on a pending order — current status: {order.status.value}"
            )

        if len(items) != len({item.product_id for item in items}):
            raise BusinessRuleError("Duplicate products in item list")

        old_qty_map: dict[UUID, int] = {
            li.product_id: li.quantity for li in order.line_items
        }

        # pass reserved quantity so the stock check is NET additional (not full quantity)
        priced_items = [
            self._validate_and_price_item(
                item, reserved=old_qty_map.get(item.product_id, 0)
            )
            for item in items
        ]

        new_qty_map: dict[UUID, int] = {
            item.product_id: item.quantity for item in priced_items
        }
        self._sync_stock(old_qty_map, new_qty_map)

        self.order_repo.replace_line_items(order_id, priced_items)

        total = sum(item.subtotal for item in priced_items)
        discount = self._calculate_discount(order.user_id, priced_items)
        return self.order_repo.update_amounts(
            order_id, total, discount, total - discount
        )

    def cancel_order(self, order_id: UUID) -> OrderResponse:
        order = self.order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found")

        self._assert_transition(order.status, OrderStatus.cancelled)

        # restore stock via flush() — committed atomically with the status change below
        for item in order.line_items:
            self.product_repo.restore_stock(item.product_id, item.quantity)

        updated = self.order_repo.update_status(
            order_id, new_status=OrderStatus.cancelled
        )

        self.event_repo.create_event(
            event_type=EventType.order_cancelled,
            aggregate_type=AggregateType.order,
            aggregate_id=order_id,
            payload={"user_id": str(order.user_id), "from_status": order.status.value},
        )

        return updated

    def _construct_order_internal(self, data: OrderCreate) -> OrderCreateInternal:
        product_ids = [item.product_id for item in data.items]
        if len(product_ids) != len(set(product_ids)):
            raise BusinessRuleError(
                "Duplicate products in order — use quantity > 1 for the same product"
            )

        priced_items: list[OrderItemInternal] = []
        total_amount = Decimal("0")

        for item in data.items:
            priced = self._validate_and_price_item(item)
            priced_items.append(priced)
            total_amount += priced.subtotal

        discount_amount = self._calculate_discount(data.user_id, priced_items)
        final_amount = total_amount - discount_amount

        return OrderCreateInternal(
            **data.model_dump(
                exclude={"items"}
            ),  # exclude: items are a different type here
            items=priced_items,
            total_amount=total_amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
        )

    def _validate_and_price_item(
        self, item: OrderItemCreate, reserved: int = 0
    ) -> OrderItemInternal:
        product = self.product_repo.get_by_id(item.product_id)

        if product is None:
            raise NotFoundError(f"Product {item.product_id} not found")
        if product.status != ProductStatus.available:
            raise BusinessRuleError(
                f"Product {item.product_id} ('{product.name}') is not available — "
                f"status: {product.status}"
            )

        # reserved = quantity already held by this order; only the NET additional must be in stock
        additional_needed = item.quantity - reserved
        if additional_needed > 0 and product.stock_quantity < additional_needed:
            raise BusinessRuleError(
                f"Insufficient stock for '{product.name}': "
                f"need {additional_needed} more, have {product.stock_quantity}"
            )

        unit_price = Decimal(str(product.price))
        return OrderItemInternal(
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=unit_price,
            subtotal=unit_price * item.quantity,
        )

    def _sync_stock(
        self,
        old_qty_map: dict[UUID, int],
        new_qty_map: dict[UUID, int],
    ) -> None:
        for product_id in old_qty_map.keys() | new_qty_map.keys():
            old_qty = old_qty_map.get(product_id, 0)
            new_qty = new_qty_map.get(product_id, 0)
            if new_qty > old_qty:
                self.product_repo.deduct_stock(product_id, new_qty - old_qty)
            elif new_qty < old_qty:
                self.product_repo.restore_stock(product_id, old_qty - new_qty)

    def _calculate_discount(
        self, user_id: UUID, items: list[OrderItemInternal]
    ) -> Decimal:
        # no discount logic defined yet
        return Decimal("0")

    def _assert_transition(self, current: OrderStatus, target: OrderStatus) -> None:
        if target not in _VALID_TRANSITIONS[current]:
            allowed = {s.value for s in _VALID_TRANSITIONS[current]}
            raise BusinessRuleError(
                f"Cannot transition order from '{current.value}' to '{target.value}'. "
                f"Allowed next states: {allowed or 'none (terminal state)'}"
            )
