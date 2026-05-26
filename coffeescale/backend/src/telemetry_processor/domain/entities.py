"""Domain entities for telemetry_processor.

ADR-003: No external imports — stdlib only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SackState:
    device_id: str
    store_id: str
    product: str
    current_kg: float
    capacity_kg: float
    threshold_kg: float
    timestamp: str

    @property
    def needs_replenishment(self) -> bool:
        return self.current_kg < self.threshold_kg
