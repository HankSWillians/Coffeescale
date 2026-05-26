"""SQS adapter for OrderRequestPublisher port."""

import json
import os

import boto3

from shared.logging_config import get_logger
from telemetry_processor.domain.entities import SackState
from telemetry_processor.domain.ports import OrderRequestPublisher

logger = get_logger(__name__)

_sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
QUEUE_URL = os.environ.get("ORDER_BUFFER_QUEUE_URL", "")


class SqsOrderPublisher(OrderRequestPublisher):
    def publish(self, state: SackState) -> None:
        body = json.dumps(
            {
                "deviceId": state.device_id,
                "storeId": state.store_id,
                "product": state.product,
                "currentKg": float(state.current_kg),
                "capacityKg": float(state.capacity_kg),
                "thresholdKg": float(state.threshold_kg),
                "timestamp": state.timestamp,
            }
        )
        _sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=body)
        logger.info("Order request published", extra={"device_id": state.device_id})
