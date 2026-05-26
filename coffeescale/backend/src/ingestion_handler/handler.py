"""Lambda 1 — ingestion_handler.

Receives HTTP POST /telemetry from IoT devices (via API Gateway), validates
the JSON structure (NOT the HMAC — that is security_validator's job per
ADR-003 separation of concerns), and enqueues the raw payload + auth header
to SQS telemetry-queue.

No Hexagonal here: this Lambda has a single adapter (SQS) and trivial
procedural logic.  Applying Hexagonal would be over-engineering.

ADR reference: ADR-001 (EDA), ADR-002 (Serverless).
"""

import json
import os
import uuid

import boto3

from shared.logging_config import get_logger

logger = get_logger(__name__)

_sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
QUEUE_URL = os.environ["TELEMETRY_QUEUE_URL"]

REQUIRED_FIELDS = {"deviceId", "storeId", "product", "weightKg", "capacityKg", "timestamp", "nonce"}


def _bad_request(message: str, code: str = "INVALID_PAYLOAD") -> dict:
    return {
        "statusCode": 400,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message, "code": code}),
    }


def lambda_handler(event: dict, context: object) -> dict:  # noqa: ARG001
    request_id = str(uuid.uuid4())
    logger.info("Received telemetry request", extra={"request_id": request_id})

    # 1. Require Authorization header
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("HMAC-SHA256"):
        logger.warning("Missing or malformed Authorization header")
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Authorization header required", "code": "UNAUTHORIZED"}),
        }

    # 2. Parse body
    raw_body = event.get("body") or ""
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Invalid JSON body", extra={"error": str(exc)})
        return _bad_request(f"Invalid JSON: {exc}")

    # 3. Validate required fields
    missing = REQUIRED_FIELDS - set(payload.keys())
    if missing:
        return _bad_request(f"Missing fields: {sorted(missing)}")

    # 4. Basic type checks
    try:
        float(payload["weightKg"])
        float(payload["capacityKg"])
    except (TypeError, ValueError):
        return _bad_request("weightKg and capacityKg must be numbers")

    # 5. Enqueue to SQS (include auth header for security_validator)
    message = json.dumps(
        {"payload": payload, "authorization": auth_header, "request_id": request_id}
    )
    _sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=message)

    logger.info(
        "Telemetry enqueued",
        extra={"request_id": request_id, "device_id": payload.get("deviceId")},
    )
    return {
        "statusCode": 202,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": "accepted", "requestId": request_id}),
    }
