"""Abstract ports for telemetry_processor (Hexagonal Architecture).

ADR-003: All ports are ABCs.  No adapters, no boto3, no botocore imported here.
"""

from abc import ABC, abstractmethod

from telemetry_processor.domain.entities import SackState


class InventoryRepository(ABC):
    @abstractmethod
    def upsert(self, state: SackState) -> None:
        """Persist or overwrite the current sack state."""


class ThresholdProvider(ABC):
    @abstractmethod
    def get_threshold(self, product: str) -> float:
        """Return the replenishment threshold in kg for *product*."""


class OrderRequestPublisher(ABC):
    @abstractmethod
    def publish(self, state: SackState) -> None:
        """Publish a replenishment request for *state* to the order pipeline."""
