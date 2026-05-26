"""Lambda 5 — erp_dispatcher (entry point).

CRITICAL: ReservedConcurrentExecutions = 1 in template.yaml.
This is the ONLY guarantee of max 1 request/second to LogisCore ERP.
Do NOT remove this setting. See ADR-002.

Consumes SQS erp-dispatch-queue one message at a time (concurrency = 1).
Retries with exponential backoff (0.5→1→2→4→8s, max 5 attempts).
Failed orders go to erp-dlq after 5 SQS redrive attempts.

Idempotency: checks order status in DynamoDB before dispatching —
already-sent orders are skipped.

Hexagonal Architecture (ADR-003):
  Ports: ErpClient, OrderStatusUpdater, NotificationPublisher, Sleeper
  Adapters: HttpErpClient, DynamoDbStatusUpdater, SqsNotificationPublisher, RealSleeper
"""

import json
import time

from erp_dispatcher.adapters.exponential_backoff import (
    DynamoDbStatusUpdater,
    RealSleeper,
    SqsNotificationPublisher,
)
from erp_dispatcher.adapters.http_erp_client import HttpErpClient
from erp_dispatcher.domain.entities import OrderToDispatch
from erp_dispatcher.domain.use_cases import DispatchOrderToErp
from shared.logging_config import get_logger
from shared.metrics import emit

logger = get_logger(__name__)

_use_case = DispatchOrderToErp(
    erp_client=HttpErpClient(),
    status_updater=DynamoDbStatusUpdater(),
    notification_publisher=SqsNotificationPublisher(),
    sleeper=RealSleeper(),
)


def lambda_handler(event: dict, context: object) -> dict:  # noqa: ARG001
    failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        start = time.monotonic()
        try:
            body = json.loads(record["body"])
            order = OrderToDispatch(
                order_id=body["orderId"],
                store_id=body["storeId"],
                device_id=body.get("deviceId", ""),
                product=body["product"],
                quantity_kg=float(body["quantityKg"]),
                created_at=body["createdAt"],
            )
            _use_case.execute(order)
            latency_ms = (time.monotonic() - start) * 1000
            emit(
                "ErpDispatchLatencyMs",
                latency_ms,
                unit="Milliseconds",
                dimensions={"StoreId": order.store_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "ERP dispatch failed",
                extra={"message_id": message_id, "error": str(exc)},
            )
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
