"""Abstract ports for order_generator (Hexagonal Architecture).

ADR-003: No adapters, no boto3, no botocore.
"""

from abc import ABC, abstractmethod

from order_generator.domain.entities import ReplenishmentOrder


class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: ReplenishmentOrder) -> None:
        """Persist the order (DynamoDB, etc.)."""

    @abstractmethod
    def exists_for_device_in_hour(self, device_id: str, hour_bucket: str) -> bool:
        """Return True if an order already exists for this device in the current hour bucket.

        Used for idempotency: avoid generating 2 orders for the same sack within an hour.
        """


class ErpQueuePublisher(ABC):
    @abstractmethod
    def publish(self, order: ReplenishmentOrder) -> None:
        """Enqueue the order for sequential ERP dispatch."""


class BufferKgProvider(ABC):
    @abstractmethod
    def get_buffer_kg(self) -> float:
        """Return the buffer quantity to add to the replenishment order."""
