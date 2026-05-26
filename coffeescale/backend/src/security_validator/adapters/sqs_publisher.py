"""SQS adapter for ValidPacketPublisher port."""

import json
import os

import boto3

from security_validator.domain.entities import TelemetryPacket
from security_validator.domain.ports import ValidPacketPublisher
from shared.logging_config import get_logger

logger = get_logger(__name__)

_sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
QUEUE_URL = os.environ.get("VALIDATED_QUEUE_URL", "")


class SqsValidPacketPublisher(ValidPacketPublisher):
    def publish(self, packet: TelemetryPacket) -> None:
        body = json.dumps(
            {
                "deviceId": packet.device_id,
                "storeId": packet.store_id,
                "product": packet.product,
                "weightKg": packet.weight_kg,
                "capacityKg": packet.capacity_kg,
                "timestamp": packet.timestamp,
                "nonce": packet.nonce,
            }
        )
        _sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=body)
        logger.info("Valid packet published", extra={"device_id": packet.device_id})
