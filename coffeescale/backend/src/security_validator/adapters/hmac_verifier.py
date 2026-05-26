"""HMAC-SHA256 adapter for SignatureVerifier port.

Signs the canonicalized JSON payload (keys sorted alphabetically, recursive)
using HMAC-SHA256.  Uses hmac.compare_digest to prevent timing attacks.

The simulator (Node.js) applies the same canonicalization so signatures align.
"""

import hashlib
import hmac
import json

from security_validator.domain.entities import TelemetryPacket
from security_validator.domain.ports import SignatureVerifier

# Fields included in the signed payload (matches the simulator)
_SIGNED_FIELDS = ["deviceId", "storeId", "product", "weightKg", "capacityKg", "timestamp", "nonce"]


def _js_number(n: float) -> "int | float":
    """Mimic JavaScript's JSON.stringify number serialization.

    JS serializes 20.0 as "20" (no decimal) because it has no int/float
    distinction. Python serializes 20.0 as "20.0". To produce signatures
    that match the Node.js simulator, we collapse floats with no fractional
    part to int before serialization.
    """
    if isinstance(n, float) and n.is_integer():
        return int(n)
    return n


def _canonical_json(packet: TelemetryPacket) -> bytes:
    """Build the deterministic JSON string that was signed by the device."""
    data = {
        "deviceId": packet.device_id,
        "storeId": packet.store_id,
        "product": packet.product,
        "weightKg": _js_number(packet.weight_kg),
        "capacityKg": _js_number(packet.capacity_kg),
        "timestamp": packet.timestamp,
        "nonce": packet.nonce,
    }
    # Sort keys recursively, no extra whitespace — must match simulator exactly
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

class HmacVerifier(SignatureVerifier):
    """Implements SignatureVerifier using HMAC-SHA256."""

    def verify(self, packet: TelemetryPacket, secret: str) -> bool:
        message = _canonical_json(packet)
        expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        # compare_digest prevents timing-based side channels
        return hmac.compare_digest(expected, packet.signature_hex)
