"""Lambda 2 — security_validator (entry point).

Consumes SQS telemetry-queue in batches of 10.  Verifies HMAC-SHA256
on each packet.  Valid packets flow to validated-telemetry-queue; invalid
packets are logged/metriced and silently discarded.

Hexagonal Architecture (ADR-003):
  Ports: SignatureVerifier, AuditLogger, ValidPacketPublisher
  Adapters: HmacVerifier, CloudWatchAuditLogger, SqsValidPacketPublisher

HMAC secret is fetched from Parameter Store with 60 s in-memory cache.
"""

import json

from security_validator.adapters.cloudwatch_audit import CloudWatchAuditLogger
from security_validator.adapters.hmac_verifier import HmacVerifier
from security_validator.adapters.sqs_publisher import SqsValidPacketPublisher
from security_validator.domain.entities import TelemetryPacket
from security_validator.domain.use_cases import ValidateTelemetryPacket
from shared.logging_config import get_logger
from shared.parameter_store import get_parameter

logger = get_logger(__name__)

HMAC_SECRET_PATH = "/coffeescale/hmac/secret"

_use_case = ValidateTelemetryPacket(
    verifier=HmacVerifier(),
    audit_logger=CloudWatchAuditLogger(),
    publisher=SqsValidPacketPublisher(),
)


def _parse_auth_header(header: str) -> str:
    """Extract the hex signature from 'HMAC-SHA256 keyId=..., signature=<hex>'."""
    for part in header.split(","):
        part = part.strip()
        if part.startswith("signature="):
            return part.split("=", 1)[1].strip()
    return ""


def lambda_handler(event: dict, context: object) -> dict:  # noqa: ARG001
    secret = get_parameter(HMAC_SECRET_PATH)
    results = {"batchItemFailures": []}

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            body = json.loads(record["body"])
            payload = body.get("payload", body)  # support wrapped and unwrapped formats
            auth_header = body.get("authorization", "")
            signature = _parse_auth_header(auth_header)

            packet = TelemetryPacket(
                device_id=payload["deviceId"],
                store_id=payload["storeId"],
                product=payload["product"],
                weight_kg=float(payload["weightKg"]),
                capacity_kg=float(payload["capacityKg"]),
                timestamp=payload["timestamp"],
                nonce=payload["nonce"],
                signature_hex=signature,
            )
            _use_case.execute(packet, secret)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to process record",
                extra={"message_id": message_id, "error": str(exc)},
            )
            results["batchItemFailures"].append({"itemIdentifier": message_id})

    return results
