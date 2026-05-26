"""Concrete Sleeper and DynamoDB/SQS adapters for erp_dispatcher."""

import json
import os
import time

import boto3

from erp_dispatcher.domain.entities import OrderToDispatch
from erp_dispatcher.domain.ports import NotificationPublisher, OrderStatusUpdater, Sleeper
from shared.logging_config import get_logger

logger = get_logger(__name__)

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
_sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))

ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "orders")
NOTIFICATION_QUEUE_URL = os.environ.get("NOTIFICATION_QUEUE_URL", "")


class RealSleeper(Sleeper):
    """Production sleeper — delegates to time.sleep."""

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class DynamoDbStatusUpdater(OrderStatusUpdater):
    def __init__(self, table_name: str = ORDERS_TABLE) -> None:
        self._table = _dynamodb.Table(table_name)

    def update(self, order_id: str, status: str) -> None:
        self._table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status},
        )
        logger.info("Order status updated", extra={"order_id": order_id, "status": status})


class SqsNotificationPublisher(NotificationPublisher):
    def publish_success(self, order: OrderToDispatch) -> None:
        if not NOTIFICATION_QUEUE_URL:
            return
        body = json.dumps(
            {
                "orderId": order.order_id,
                "storeId": order.store_id,
                "product": order.product,
                "quantityKg": order.quantity_kg,
            }
        )
        _sqs.send_message(QueueUrl=NOTIFICATION_QUEUE_URL, MessageBody=body)
        logger.info("Notification queued", extra={"order_id": order.order_id})
