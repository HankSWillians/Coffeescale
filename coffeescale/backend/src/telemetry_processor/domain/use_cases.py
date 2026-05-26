"""Use cases for telemetry_processor.

ADR-003: Pure orchestration of ports.  No infrastructure, no AWS SDK.
"""

from telemetry_processor.domain.entities import SackState
from telemetry_processor.domain.ports import (
    InventoryRepository,
    OrderRequestPublisher,
    ThresholdProvider,
)


class ProcessTelemetry:
    """Upsert inventory state and conditionally trigger a replenishment order."""

    def __init__(
        self,
        inventory: InventoryRepository,
        threshold_provider: ThresholdProvider,
        order_publisher: OrderRequestPublisher,
    ) -> None:
        self._inventory = inventory
        self._thresholds = threshold_provider
        self._orders = order_publisher

    def execute(self, packet: dict) -> SackState:
        """Process one validated telemetry packet.

        Args:
            packet: Dict with keys matching the TelemetryPacket JSON schema.

        Returns:
            The persisted SackState (useful for testing).
        """
        threshold = self._thresholds.get_threshold(packet["product"])
        state = SackState(
            device_id=packet["deviceId"],
            store_id=packet["storeId"],
            product=packet["product"],
            current_kg=float(packet["weightKg"]),
            capacity_kg=float(packet["capacityKg"]),
            threshold_kg=threshold,
            timestamp=packet["timestamp"],
        )

        self._inventory.upsert(state)

        if state.needs_replenishment:
            self._orders.publish(state)

        return state
