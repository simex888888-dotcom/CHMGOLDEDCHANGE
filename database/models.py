import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, DateTime, Enum, Numeric, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrderStatus(str, PyEnum):
    pending = "pending"
    approved = "approved"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_from: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    amount_to: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    base_rate: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    our_rate: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    commission: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    requisites: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.pending
    )
    cxc_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} direction={self.direction} status={self.status}>"


class RateCache(Base):
    __tablename__ = "rate_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pair: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    rate: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<RateCache pair={self.pair} rate={self.rate}>"
