"""DynamoDB adapter for OrderRepository port.

Partition key: order_id (String).
TTL attribute: expires_at (30 days from creation).
Hour-bucket deduplication uses a GSI query on device_id + hour_bucket.

DECISION: Rather than adding a GSI (which adds cost and complexity), we use
a composite item with pk=device_id#hour and sk=order_id in a separate
'dedup' item stored alongside the main order.  This keeps the table simple.
"""

import os
import time
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from order_generator.domain.entities import ReplenishmentOrder
from order_generator.domain.ports import OrderRepository
from shared.logging_config import get_logger

logger = get_logger(__name__)

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
TABLE_NAME = os.environ.get("ORDERS_TABLE", "orders")
THIRTY_DAYS_S = 30 * 24 * 3600


class DynamoDbOrderRepository(OrderRepository):
    def __init__(self, table_name: str = TABLE_NAME) -> None:
        self._table = _dynamodb.Table(table_name)

    def save(self, order: ReplenishmentOrder) -> None:
        expires_at = int(time.time()) + THIRTY_DAYS_S
        self._table.put_item(
            Item={
                "order_id": order.order_id,
                "store_id": order.store_id,
                "device_id": order.device_id,
                "product": order.product,
                "quantity_kg": Decimal(str(order.quantity_kg)),
                "created_at": order.created_at,
                "status": order.status,
                "expires_at": expires_at,
                # Dedup key stored inline for exists_for_device_in_hour
                "dedup_key": f"{order.device_id}#{order.created_at[:13]}",
            }
        )
        logger.info("Order saved", extra={"order_id": order.order_id})

    def exists_for_device_in_hour(self, device_id: str, hour_bucket: str) -> bool:
        dedup_key = f"{device_id}#{hour_bucket}"
        response = self._table.query(
            IndexName="dedup-index",
            KeyConditionExpression=Key("dedup_key").eq(dedup_key),
            Limit=1,
        )
        return bool(response.get("Items"))
