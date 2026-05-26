"""CloudWatch audit adapter for AuditLogger port.

Emits a custom metric SecurityFailures and logs a structured rejection record.
"""

from security_validator.domain.entities import TelemetryPacket
from security_validator.domain.ports import AuditLogger
from shared.logging_config import get_logger
from shared.metrics import emit

logger = get_logger(__name__)


class CloudWatchAuditLogger(AuditLogger):
    """Logs security rejections to CloudWatch Logs + custom metrics."""

    def log_rejection(self, packet: TelemetryPacket, reason: str) -> None:
        logger.warning(
            "Telemetry packet rejected",
            extra={
                "device_id": packet.device_id,
                "store_id": packet.store_id,
                "reason": reason,
                "nonce": packet.nonce,
            },
        )
        emit(
            metric_name="SecurityFailures",
            value=1,
            unit="Count",
            dimensions={"StoreId": packet.store_id},
        )
