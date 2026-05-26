"""Use cases for security_validator.

Orchestrates ports only.  No infrastructure concerns.
ADR-003: Pure domain logic — imports only from domain/ and stdlib.
"""

from security_validator.domain.entities import TelemetryPacket, ValidationResult
from security_validator.domain.ports import AuditLogger, SignatureVerifier, ValidPacketPublisher


class ValidateTelemetryPacket:
    """Verify the HMAC signature and route the packet accordingly."""

    def __init__(
        self,
        verifier: SignatureVerifier,
        audit_logger: AuditLogger,
        publisher: ValidPacketPublisher,
    ) -> None:
        self._verifier = verifier
        self._audit = audit_logger
        self._publisher = publisher

    def execute(self, packet: TelemetryPacket, secret: str) -> ValidationResult:
        if not self._verifier.verify(packet, secret):
            reason = "Invalid HMAC-SHA256 signature"
            self._audit.log_rejection(packet, reason)
            return ValidationResult(packet=packet, is_valid=False, reason=reason)

        self._publisher.publish(packet)
        return ValidationResult(packet=packet, is_valid=True)
