"""Pydantic models for orders, items and status transitions."""
from __future__ import annotations

import enum
import logging
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OrderStatus(str, enum.Enum):
    pending = "pending"
    preparing = "preparing"
    completed = "completed"

    @property
    def label(self) -> str:
        return {
            OrderStatus.pending: "Pendiente",
            OrderStatus.preparing: "En preparación",
            OrderStatus.completed: "Completada",
        }[self]

    @classmethod
    def list(cls) -> list["OrderStatus"]:
        return [OrderStatus.pending, OrderStatus.preparing, OrderStatus.completed]


class DeliveryType(str, enum.Enum):
    delivery = "delivery"
    pickup = "pickup"

    @property
    def label(self) -> str:
        return {
            DeliveryType.delivery: "Delivery",
            DeliveryType.pickup: "Pickup (retiro en local)",
        }[self]


class OrderItem(BaseModel):
    name: str
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(default=0.0, ge=0)

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class Order(BaseModel):
    id: int | None = None
    number: int
    status: OrderStatus = OrderStatus.pending
    items: list[OrderItem] = Field(default_factory=list)
    delivery_type: DeliveryType = DeliveryType.pickup
    customer_name: str = ""
    delivery_phone: str = ""
    delivery_address: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @property
    def total(self) -> float:
        return round(sum(item.total for item in self.items), 2)

    @property
    def elapsed_seconds(self) -> int:
        return int((datetime.now() - self.created_at).total_seconds())

    def to_dict(self) -> dict:
        """JSON-safe representation for WebSocket broadcasts and the API."""
        return {
            "id": self.id,
            "number": self.number,
            "status": self.status.value,
            "status_label": self.status.label,
            "items": [
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total": item.total,
                }
                for item in self.items
            ],
            "delivery_type": self.delivery_type.value,
            "delivery_label": self.delivery_type.label,
            "customer_name": self.customer_name,
            "delivery_phone": self.delivery_phone,
            "delivery_address": self.delivery_address,
            "total": self.total,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "elapsed_seconds": self.elapsed_seconds,
        }
