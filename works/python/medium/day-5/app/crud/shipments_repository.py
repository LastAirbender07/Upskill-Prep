from typing import Optional
from uuid import UUID
from datetime import date
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.shipments import Shipment
from app.schemas.shipments import ShipmentCreate, ShipmentResponse
from app.schemas.enums import ShipmentStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class ShipmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_shipment(self, data: ShipmentCreate) -> ShipmentResponse:
        shipment_orm = Shipment(**data.model_dump())
        self.db.add(shipment_orm)

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.exception("Failed to create shipment due to integrity error")
            # two possible causes:
            # 1. order_id already has a shipment (unique=True on order_id)
            # 2. carrier + tracking_number combination already exists
            raise ValueError("Shipment creation failed due to integrity error") from e

        self.db.refresh(shipment_orm)
        logger.info(f"Created shipment {shipment_orm.id} for order {data.order_id}")
        return ShipmentResponse.model_validate(shipment_orm)

    def get_by_id(self, shipment_id: UUID) -> ShipmentResponse | None:
        shipment_orm = self.db.query(Shipment).filter(Shipment.id == shipment_id).first()

        if shipment_orm is None:
            return None

        return ShipmentResponse.model_validate(shipment_orm)

    def get_by_order(self, order_id: UUID) -> ShipmentResponse | None:
        shipment_orm = self.db.query(Shipment).filter(Shipment.order_id == order_id).first()

        if shipment_orm is None:
            return None

        return ShipmentResponse.model_validate(shipment_orm)

    def get_overdue(self) -> list[ShipmentResponse]:
        # shipments past their estimated delivery date and not yet delivered
        shipments = (
            self.db.query(Shipment)
            .filter(
                Shipment.estimated_delivery_date < func.current_date(),
                Shipment.status != ShipmentStatus.delivered,
                Shipment.status != ShipmentStatus.returned,
            )
            .all()
        )
        return [ShipmentResponse.model_validate(s) for s in shipments]

    def update_status(
        self,
        shipment_id: UUID,
        new_status: ShipmentStatus,
        tracking_number: Optional[str] = None,
        actual_delivery_date: Optional[date] = None,
    ) -> ShipmentResponse | None:
        shipment_orm = self.db.query(Shipment).filter(Shipment.id == shipment_id).first()

        if shipment_orm is None:
            return None

        shipment_orm.status = new_status

        if tracking_number is not None:
            shipment_orm.tracking_number = tracking_number

        if actual_delivery_date is not None:
            shipment_orm.actual_delivery_date = actual_delivery_date

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            # carrier + tracking_number unique constraint
            raise ValueError("Shipment update failed — duplicate tracking number for this carrier") from e

        self.db.refresh(shipment_orm)
        return ShipmentResponse.model_validate(shipment_orm)
