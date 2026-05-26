"""SQS adapter for ErpQueuePublisher port — sends orders to erp-dispatch-queue."""

import json
import os

import boto3

from order_generator.domain.entities import ReplenishmentOrder
from order_generator.domain.ports import ErpQueuePublisher
from shared.logging_config import get_logger

logger = get_logger(__name__)

_sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
QUEUE_URL = os.environ.get("ERP_DISPATCH_QUEUE_URL", "")


class SqsErpQueuePublisher(ErpQueuePublisher):
    def publish(self, order: ReplenishmentOrder) -> None:
        body = json.dumps(
            {
                "orderId": order.order_id,
                "storeId": order.store_id,
                "deviceId": order.device_id,
                "product": order.product,
                "quantityKg": order.quantity_kg,
                "createdAt": order.created_at,
                "status": order.status,
            }
        )
        _sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=body)
        logger.info("Order queued for ERP dispatch", extra={"order_id": order.order_id})


class ParameterStoreBufferKgProvider:
    """Reads buffer_kg from Parameter Store.  Placed here to avoid a new file for a tiny class."""

    def get_buffer_kg(self) -> float:
        from shared.parameter_store import get_parameter  # noqa: PLC0415

        try:
            return float(get_parameter("/coffeescale/buffer_kg"))
        except Exception:  # noqa: BLE001
            return 2.0  # sensible default
