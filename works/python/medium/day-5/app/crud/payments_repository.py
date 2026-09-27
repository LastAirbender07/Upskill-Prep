from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.payments import Payment
from app.schemas.payments import PaymentCreateInternal, PaymentResponse
from app.schemas.enums import PaymentStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_payment(self, data: PaymentCreateInternal) -> PaymentResponse:
        payment_orm = Payment(**data.model_dump())
        self.db.add(payment_orm)

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.exception("Failed to create payment due to integrity error")
            raise ValueError("Payment creation failed due to integrity error") from e

        self.db.refresh(payment_orm)
        logger.info(f"Created payment {payment_orm.id} for order {data.order_id}")
        return PaymentResponse.model_validate(payment_orm)

    def get_by_id(self, payment_id: UUID) -> PaymentResponse | None:
        payment_orm = self.db.query(Payment).filter(Payment.id == payment_id).first()

        if payment_orm is None:
            return None

        return PaymentResponse.model_validate(payment_orm)

    def get_by_order(self, order_id: UUID) -> list[PaymentResponse]:
        # an order can have multiple payment attempts — returns all of them
        payments = self.db.query(Payment).filter(Payment.order_id == order_id).all()
        return [PaymentResponse.model_validate(payment) for payment in payments]

    def get_completed_by_order(self, order_id: UUID) -> PaymentResponse | None:
        # at most one payment per order can be completed — used by service to prevent double payment
        payment_orm = (
            self.db.query(Payment)
            .filter(Payment.order_id == order_id, Payment.status == PaymentStatus.completed)
            .first()
        )

        if payment_orm is None:
            return None

        return PaymentResponse.model_validate(payment_orm)

    def update_status(
        self,
        payment_id: UUID,
        new_status: PaymentStatus,
        transaction_ref: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> PaymentResponse | None:
        payment_orm = self.db.query(Payment).filter(Payment.id == payment_id).first()

        if payment_orm is None:
            return None

        payment_orm.status = new_status

        if transaction_ref is not None:
            payment_orm.transaction_ref = transaction_ref

        if failure_reason is not None:
            payment_orm.failure_reason = failure_reason

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            # transaction_ref has unique=True — duplicate ref from gateway would trigger this
            raise ValueError("Payment update failed — duplicate transaction reference") from e

        self.db.refresh(payment_orm)
        return PaymentResponse.model_validate(payment_orm)

    def get_orm_by_id(self, payment_id: UUID) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()
