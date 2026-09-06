from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database.base import Base


# got from: https://docs.sqlalchemy.org/en/20/orm/quickstart.html
class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    fullname: Mapped[Optional[str]] = mapped_column(String(30))

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"


class EventMetadata(Base):
    __tablename__ = "event_metadata"

    event_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    event_type: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source: Mapped[str] = mapped_column(String(25))
    event_metadata: Mapped[dict] = mapped_column(JSONB)
