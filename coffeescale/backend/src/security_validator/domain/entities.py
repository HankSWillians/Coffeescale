"""Domain entities for security_validator.

Pure dataclasses — no AWS SDK, no adapters, no I/O.
ADR-003: domain/ must not import from adapters/, boto3, or botocore.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryPacket:
    device_id: str
    store_id: str
    product: str
    weight_kg: float
    capacity_kg: float
    timestamp: str
    nonce: str
    signature_hex: str


@dataclass(frozen=True)
class ValidationResult:
    packet: TelemetryPacket
    is_valid: bool
    reason: str | None = None
