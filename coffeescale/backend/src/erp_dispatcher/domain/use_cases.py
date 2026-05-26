"""Use cases for erp_dispatcher.

Retry policy: exponential backoff 0.5→1→2→4→8 seconds, max 5 attempts.
ADR-003: Pure orchestration — no urllib3, no boto3.
"""

from erp_dispatcher.domain.entities import ErpResponse, OrderToDispatch
from erp_dispatcher.domain.ports import (
    ErpClient,
    NotificationPublisher,
    OrderStatusUpdater,
    Sleeper,
)

MAX_ATTEMPTS = 5
BASE_DELAY = 0.5  # seconds


class DispatchOrderToErp:
    def __init__(
        self,
        erp_client: ErpClient,
        status_updater: OrderStatusUpdater,
        notification_publisher: NotificationPublisher,
        sleeper: Sleeper,
    ) -> None:
        self._client = erp_client
        self._updater = status_updater
        self._notifier = notification_publisher
        self._sleeper = sleeper

    def execute(self, order: OrderToDispatch) -> ErpResponse:
        """Send the order to the ERP with exponential backoff.

        Returns the last ErpResponse (success or final failure).
        Raises RuntimeError after MAX_ATTEMPTS failed attempts.
        """
        last_response: ErpResponse | None = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._client.send(order)
            except Exception as exc:  # noqa: BLE001
                last_response = ErpResponse(success=False, status_code=0, body=str(exc))
            else:
                last_response = response
                if response.success:
                    self._updater.update(order.order_id, "sent")
                    self._notifier.publish_success(order)
                    return response

            if attempt < MAX_ATTEMPTS - 1:
                delay = BASE_DELAY * (2**attempt)
                self._sleeper.sleep(delay)

        self._updater.update(order.order_id, "failed")
        raise RuntimeError(
            f"ERP dispatch failed after {MAX_ATTEMPTS} attempts for order {order.order_id}. "
            f"Last response: {last_response}"
        )
