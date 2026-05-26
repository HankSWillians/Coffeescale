"""Lambda 3 — telemetry_processor (entry point).

Consumes SQS validated-telemetry-queue.  Upserts inventory state in DynamoDB
and publishes to order-buffer when weight < threshold.

Hexagonal Architecture (ADR-003):
  Ports: InventoryRepository, ThresholdProvider, OrderRequestPublisher
  Adapters: DynamoDbInventoryRepository, ParameterStoreThresholdProvider, SqsOrderPublisher

Idempotency: put_item overwrites with last-writer-wins semantics.
At-least-once delivery is safe because DynamoDB upsert is deterministic
for the same device_id + timestamp combination.
"""

import json

from shared.logging_config import get_logger
from telemetry_processor.adapters.dynamodb_inventory import DynamoDbInventoryRepository
from telemetry_processor.adapters.parameter_store_thresholds import ParameterStoreThresholdProvider
from telemetry_processor.adapters.sqs_order_publisher import SqsOrderPublisher
from telemetry_processor.domain.use_cases import ProcessTelemetry

logger = get_logger(__name__)

_use_case = ProcessTelemetry(
    inventory=DynamoDbInventoryRepository(),
    threshold_provider=ParameterStoreThresholdProvider(),
    order_publisher=SqsOrderPublisher(),
)


def lambda_handler(event: dict, context: object) -> dict:  # noqa: ARG001
    failures = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            packet = json.loads(record["body"])
            state = _use_case.execute(packet)
            logger.info(
                "Telemetry processed",
                extra={
                    "device_id": state.device_id,
                    "needs_replenishment": state.needs_replenishment,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to process telemetry",
                extra={"message_id": message_id, "error": str(exc)},
            )
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
