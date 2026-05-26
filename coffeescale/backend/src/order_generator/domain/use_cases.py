"""Use cases for order_generator.

ADR-003: Pure orchestration — no infrastructure imports.
"""

import uuid
from datetime import UTC, datetime

from order_generator.domain.entities import ReplenishmentOrder
from order_generator.domain.ports import BufferKgProvider, ErpQueuePublisher, OrderRepository


class GenerateOrder:
    """Create and persist a ReplenishmentOrder from a SackState message."""

    def __init__(
        self,
        repository: OrderRepository,
        publisher: ErpQueuePublisher,
        buffer_provider: BufferKgProvider,
    ) -> None:
        self._repo = repository
        self._publisher = publisher
        self._buffer = buffer_provider

    def execute(self, message: dict) -> ReplenishmentOrder | None:
        """Generate an order if one does not already exist for this device this hour.

        Idempotency: device_id + hour_bucket deduplication.
        Returns None if order was skipped (already exists).
        """
        device_id = message["deviceId"]
        hour_bucket = datetime.now(UTC).strftime("%Y-%m-%dT%H")

        if self._repo.exists_for_device_in_hour(device_id, hour_bucket):
            return None

        capacity_kg = float(message["capacityKg"])
        current_kg = float(message["currentKg"])
        buffer_kg = self._buffer.get_buffer_kg()
        quantity = max(0.0, capacity_kg - current_kg + buffer_kg)

        order = ReplenishmentOrder(
            order_id=str(uuid.uuid4()),
            store_id=message["storeId"],
            device_id=device_id,
            product=message["product"],
            quantity_kg=round(quantity, 2),
            created_at=datetime.now(UTC).isoformat(),
            status="pending",
        )

        self._repo.save(order)
        self._publisher.publish(order)
        return order
