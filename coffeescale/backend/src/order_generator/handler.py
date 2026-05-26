"""Lambda 4 — order_generator (entry point).

Consumes SQS order-buffer.  Generates a ReplenishmentOrder, persists it
in DynamoDB orders table, and queues it for sequential ERP dispatch.

Hexagonal Architecture (ADR-003):
  Ports: OrderRepository, ErpQueuePublisher, BufferKgProvider
  Adapters: DynamoDbOrderRepository, SqsErpQueuePublisher, ParameterStoreBufferKgProvider

Idempotency: device_id + hour_bucket dedup via DynamoDB dedup-index GSI.

ADR reference: ADR-001 (EDA), ADR-003 (Hexagonal).
"""

import json

from order_generator.adapters.dynamodb_orders import DynamoDbOrderRepository
from order_generator.adapters.sqs_notification import (
    ParameterStoreBufferKgProvider,
    SqsErpQueuePublisher,
)
from order_generator.domain.use_cases import GenerateOrder
from shared.logging_config import get_logger
from shared.metrics import emit

logger = get_logger(__name__)

_use_case = GenerateOrder(
    repository=DynamoDbOrderRepository(),
    publisher=SqsErpQueuePublisher(),
    buffer_provider=ParameterStoreBufferKgProvider(),
)


def lambda_handler(event: dict, context: object) -> dict:  # noqa: ARG001
    failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            message = json.loads(record["body"])
            order = _use_case.execute(message)
            if order:
                emit("OrdersGenerated", 1, dimensions={"StoreId": order.store_id})
                logger.info("Order generated", extra={"order_id": order.order_id})
            else:
                logger.info(
                    "Order skipped (duplicate within hour)",
                    extra={"device_id": message.get("deviceId")},
                )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to generate order",
                extra={"message_id": message_id, "error": str(exc)},
            )
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
