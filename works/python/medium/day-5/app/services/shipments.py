from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from app.crud.shipments_repository import ShipmentRepository
from app.schemas.shipments import ShipmentCreate, ShipmentResponse
from app.schemas.enums import ShipmentStatus
from app.core.exceptions import NotFoundError, ConflictError, BusinessRuleError
from app.core.logger import get_logger

logger = get_logger(__name__)

# allowed state machine transitions
_VALID_TRANSITIONS: dict[ShipmentStatus, set[ShipmentStatus]] = {
    ShipmentStatus.preparing: {ShipmentStatus.dispatched},
    ShipmentStatus.dispatched: {ShipmentStatus.in_transit},
    ShipmentStatus.in_transit: {ShipmentStatus.delivered, ShipmentStatus.returned},
    ShipmentStatus.delivered: set(),  # terminal
    ShipmentStatus.returned: set(),  # terminal
}


class ShipmentService:
    def __init__(self, db: Session):
        self.repo = ShipmentRepository(db)

    def create_shipment(self, data: ShipmentCreate) -> ShipmentResponse:
        # one-to-one — an order can have at most one shipment
        if self.repo.get_by_order(data.order_id):
            raise ConflictError(f"A shipment for order {data.order_id} already exists")
        return self.repo.create_shipment(data)

    def get_shipment(self, shipment_id: UUID) -> ShipmentResponse:
        shipment = self.repo.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Shipment {shipment_id} not found")
        return shipment

    def get_by_order(self, order_id: UUID) -> ShipmentResponse:
        shipment = self.repo.get_by_order(order_id)
        if shipment is None:
            raise NotFoundError(f"No shipment found for order {order_id}")
        return shipment

    def get_overdue(self) -> list[ShipmentResponse]:
        return self.repo.get_overdue()

    def dispatch(self, shipment_id: UUID, tracking_number: str) -> ShipmentResponse:
        """preparing -> dispatched. tracking_number is required at this point."""
        shipment = self.repo.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Shipment {shipment_id} not found")

        self._assert_transition(shipment.status, ShipmentStatus.dispatched)

        updated = self.repo.update_shipment(
            shipment_id,
            new_status=ShipmentStatus.dispatched,
            tracking_number=tracking_number,
        )
        logger.info(
            f"Shipment {shipment_id} dispatched with tracking {tracking_number}"
        )
        return updated

    def mark_in_transit(self, shipment_id: UUID) -> ShipmentResponse:
        """dispatched -> in_transit."""
        shipment = self.repo.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Shipment {shipment_id} not found")

        self._assert_transition(shipment.status, ShipmentStatus.in_transit)

        return self.repo.update_shipment(
            shipment_id, new_status=ShipmentStatus.in_transit
        )

    def mark_delivered(
        self, shipment_id: UUID, actual_delivery_date: date
    ) -> ShipmentResponse:
        """in_transit -> delivered. actual_delivery_date is required."""
        shipment = self.repo.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Shipment {shipment_id} not found")

        self._assert_transition(shipment.status, ShipmentStatus.delivered)

        updated = self.repo.update_shipment(
            shipment_id,
            new_status=ShipmentStatus.delivered,
            actual_delivery_date=actual_delivery_date,
        )
        logger.info(f"Shipment {shipment_id} delivered on {actual_delivery_date}")
        return updated

    def mark_returned(self, shipment_id: UUID) -> ShipmentResponse:
        """in_transit -> returned."""
        shipment = self.repo.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Shipment {shipment_id} not found")

        self._assert_transition(shipment.status, ShipmentStatus.returned)

        updated = self.repo.update_shipment(
            shipment_id, new_status=ShipmentStatus.returned
        )
        logger.info(f"Shipment {shipment_id} marked as returned")
        return updated

    def _assert_transition(
        self, current: ShipmentStatus, target: ShipmentStatus
    ) -> None:
        if target not in _VALID_TRANSITIONS[current]:
            allowed = {s.value for s in _VALID_TRANSITIONS[current]}
            raise BusinessRuleError(
                f"Cannot transition shipment from '{current.value}' to '{target.value}'. "
                f"Allowed next states: {allowed or 'none (terminal state)'}"
            )
