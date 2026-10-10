from uuid import UUID
from sqlalchemy.orm import Session
from app.crud.payments_repository import PaymentRepository
from app.crud.orders_repository import OrderRepository
from app.crud.users_repository import UsersRepository
from app.crud.event_logs_repository import EventLogRepository
from app.schemas.payments import PaymentCreate, PaymentCreateInternal, PaymentResponse
from app.schemas.enums import PaymentStatus, OrderStatus, EventType, AggregateType
from app.core.logger import get_logger

logger = get_logger(__name__)

_VALID_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    PaymentStatus.pending: {PaymentStatus.processing},
    PaymentStatus.processing: {PaymentStatus.completed, PaymentStatus.failed},
    PaymentStatus.failed: {PaymentStatus.pending},  # retry path
    PaymentStatus.completed: {PaymentStatus.refunded},
    PaymentStatus.refunded: set(),  # terminal
}


class PaymentService:
    def __init__(self, db: Session):
        self.repo = PaymentRepository(db)
        self.order_repo = OrderRepository(db)
        self.user_repo = UsersRepository(db)
        self.event_repo = EventLogRepository(db)

    def initiate_payment(self, data: PaymentCreate) -> PaymentResponse:
        if self.repo.get_completed_by_order(data.order_id):
            raise ValueError(f"Order {data.order_id} already has a completed payment")

        order = self.order_repo.get_by_id(data.order_id)
        if order is None:
            raise ValueError(f"Order {data.order_id} not found")

        data_internal = PaymentCreateInternal(
            **data.model_dump(), amount=order.final_amount
        )
        return self.repo.create_payment(data_internal)

    def get_payment(self, payment_id: UUID) -> PaymentResponse:
        payment = self.repo.get_by_id(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")
        return payment

    def get_by_order(self, order_id: UUID) -> list[PaymentResponse]:
        return self.repo.get_by_order(order_id)

    def mark_processing(self, payment_id: UUID) -> PaymentResponse:
        """pending → processing. Called when the payment gateway picks up the request."""
        payment = self.repo.get_by_id(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")

        self._assert_transition(payment.status, PaymentStatus.processing)
        return self.repo.update_status(payment_id, new_status=PaymentStatus.processing)

    def confirm_payment(
        self, payment_id: UUID, transaction_ref: str
    ) -> PaymentResponse:
        """processing → completed. Called when the gateway confirms success."""
        payment = self.repo.get_by_id(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")

        self._assert_transition(payment.status, PaymentStatus.completed)

        updated = self.repo.update_status(
            payment_id,
            new_status=PaymentStatus.completed,
            transaction_ref=transaction_ref,
        )

        # side effect 1: move order to confirmed
        order = self.order_repo.get_by_id(payment.order_id)
        self.order_repo.update_status(
            payment.order_id, new_status=OrderStatus.confirmed
        )

        # side effect 2: update user's lifetime spend
        if order is not None:
            self.user_repo.update_total_spent(order.user_id, order.final_amount)

        # side effect 3: log event
        self.event_repo.create_event(
            event_type=EventType.payment_completed,
            aggregate_type=AggregateType.payment,
            aggregate_id=payment_id,
            payload={
                "transaction_ref": transaction_ref,
                "order_id": str(payment.order_id),
            },
        )

        logger.info(
            f"Payment {payment_id} confirmed — transaction ref {transaction_ref}"
        )
        return updated

    def fail_payment(self, payment_id: UUID, reason: str) -> PaymentResponse:
        """processing → failed. Called when the gateway reports failure."""
        payment = self.repo.get_by_id(payment_id)
        if payment is None:
            raise ValueError(f"Payment {payment_id} not found")

        self._assert_transition(payment.status, PaymentStatus.failed)

        updated = self.repo.update_status(
            payment_id,
            new_status=PaymentStatus.failed,
            failure_reason=reason,
        )

        self.event_repo.create_event(
            event_type=EventType.payment_failed,
            aggregate_type=AggregateType.payment,
            aggregate_id=payment_id,
            payload={"failure_reason": reason, "order_id": str(payment.order_id)},
        )

        logger.info(f"Payment {payment_id} failed — reason: {reason}")
        return updated

    def _assert_transition(self, current: PaymentStatus, target: PaymentStatus) -> None:
        if target not in _VALID_TRANSITIONS[current]:
            allowed = {s.value for s in _VALID_TRANSITIONS[current]}
            raise ValueError(
                f"Cannot transition payment from '{current.value}' to '{target.value}'. "
                f"Allowed next states: {allowed or 'none (terminal state)'}"
            )
