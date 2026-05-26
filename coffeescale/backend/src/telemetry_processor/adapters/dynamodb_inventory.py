"""DynamoDB adapter for InventoryRepository port.

Partition key: device_id (String).
Uses put_item for idempotent upsert — device_id + timestamp ensures
at-least-once SQS delivery doesn't create duplicate records.
"""

import os
from decimal import Decimal

import boto3

from shared.logging_config import get_logger
from telemetry_processor.domain.entities import SackState
from telemetry_processor.domain.ports import InventoryRepository

logger = get_logger(__name__)

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
TABLE_NAME = os.environ.get("INVENTORY_TABLE", "inventory")


class DynamoDbInventoryRepository(InventoryRepository):
    def __init__(self, table_name: str = TABLE_NAME) -> None:
        self._table = _dynamodb.Table(table_name)

    def upsert(self, state: SackState) -> None:
        self._table.put_item(
            Item={
                "device_id": state.device_id,
                "store_id": state.store_id,
                "product": state.product,
                "current_kg": Decimal(str(state.current_kg)),
                "capacity_kg": Decimal(str(state.capacity_kg)),
                "threshold_kg": Decimal(str(state.threshold_kg)),
                "timestamp": state.timestamp,
                "needs_replenishment": state.needs_replenishment,
            }
        )
        logger.info("Inventory upserted", extra={"device_id": state.device_id})
