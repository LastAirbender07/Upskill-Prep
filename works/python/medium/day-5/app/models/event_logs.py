import uuid
from datetime import datetime
from sqlalchemy import String, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP as PG_TIMESTAMP, JSONB
from sqlalchemy.sql import func
from app.database.base import Base


class EventLog(Base):
    __tablename__ = "event_logs"

    __table_args__ = (
        # composite index — queries always filter by both aggregate_type AND aggregate_id together
        Index("ix_event_logs_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_event_logs_occurred_at", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(30), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        PG_TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
