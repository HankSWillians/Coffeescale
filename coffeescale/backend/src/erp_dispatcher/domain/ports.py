"""Abstract ports for erp_dispatcher (Hexagonal Architecture).

ADR-003: No urllib3, no boto3, no adapters.
"""

from abc import ABC, abstractmethod

from erp_dispatcher.domain.entities import ErpResponse, OrderToDispatch


class ErpClient(ABC):
    @abstractmethod
    def send(self, order: OrderToDispatch) -> ErpResponse:
        """POST the order to the ERP system. Returns ErpResponse."""


class OrderStatusUpdater(ABC):
    @abstractmethod
    def update(self, order_id: str, status: str) -> None:
        """Update the order status in persistent storage."""


class NotificationPublisher(ABC):
    @abstractmethod
    def publish_success(self, order: OrderToDispatch) -> None:
        """Notify downstream that the order was successfully dispatched."""


class Sleeper(ABC):
    """Injectable sleep dependency — allows tests to avoid real delays."""

    @abstractmethod
    def sleep(self, seconds: float) -> None: ...
