"""Unit tests for HmacVerifier adapter and HMAC contract test.

The contract test signs with the same algorithm the Node.js simulator uses
(sorted JSON keys, no spaces, HMAC-SHA256 hex digest) to guarantee cross-
platform compatibility.
"""

import hashlib
import hmac
import json

from security_validator.adapters.hmac_verifier import HmacVerifier, _canonical_json
from security_validator.domain.entities import TelemetryPacket

SECRET = "test-secret-12345"


def _make_packet(weight_kg: float = 14.62, signature: str = "") -> TelemetryPacket:
    return TelemetryPacket(
        device_id="CS-001-D01",
        store_id="CS-001",
        product="Andina Origen — Espresso Blend",
        weight_kg=weight_kg,
        capacity_kg=20.0,
        timestamp="2026-05-18T14:47:03.142Z",
        nonce="k9x2p4q1m8",
        signature_hex=signature,
    )


def _sign(packet: TelemetryPacket, secret: str = SECRET) -> str:
    canonical = _canonical_json(packet)
    return hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()


class TestHmacVerifier:
    def setup_method(self):
        self.verifier = HmacVerifier()

    def test_valid_signature_returns_true(self):
        packet = _make_packet()
        sig = _sign(packet)
        signed = TelemetryPacket(**{**packet.__dict__, "signature_hex": sig})
        assert self.verifier.verify(signed, SECRET) is True

    def test_wrong_secret_returns_false(self):
        packet = _make_packet()
        sig = _sign(packet, "wrong-secret")
        signed = TelemetryPacket(**{**packet.__dict__, "signature_hex": sig})
        assert self.verifier.verify(signed, SECRET) is False

    def test_tampered_weight_returns_false(self):
        packet = _make_packet(weight_kg=14.62)
        sig = _sign(packet)
        tampered = _make_packet(weight_kg=0.01)
        signed = TelemetryPacket(**{**tampered.__dict__, "signature_hex": sig})
        assert self.verifier.verify(signed, SECRET) is False

    def test_empty_signature_returns_false(self):
        packet = _make_packet()
        signed = TelemetryPacket(**{**packet.__dict__, "signature_hex": ""})
        assert self.verifier.verify(signed, SECRET) is False

    # ── HMAC Contract Test ──────────────────────────────────────────────────
    def test_contract_simulator_compatible(self):
        """Verify that the Python verifier accepts a signature produced by the
        same canonicalization algorithm the Node.js simulator uses.

        Node.js equivalent:
            const msg = JSON.stringify(payload, Object.keys(payload).sort());
            const sig = crypto.createHmac('sha256', secret).update(msg).digest('hex');

        Both sides sort keys and use compact JSON with no spaces.
        """
        # Simulate what Node.js simulator would produce
        payload = {
            "deviceId": "CS-001-D01",
            "storeId": "CS-001",
            "product": "Andina Origen — Espresso Blend",
            "weightKg": 14.62,
            "capacityKg": 20.0,
            "timestamp": "2026-05-18T14:47:03.142Z",
            "nonce": "k9x2p4q1m8",
        }
        node_payload = {k: (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in payload.items()}
        node_canonical = json.dumps(node_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        node_sig = hmac.new(SECRET.encode(), node_canonical, hashlib.sha256).hexdigest()

        packet = TelemetryPacket(
            device_id=payload["deviceId"],
            store_id=payload["storeId"],
            product=payload["product"],
            weight_kg=payload["weightKg"],
            capacity_kg=payload["capacityKg"],
            timestamp=payload["timestamp"],
            nonce=payload["nonce"],
            signature_hex=node_sig,
        )
        assert self.verifier.verify(packet, SECRET) is True, (
            "Python verifier rejected a signature produced by the Node.js algorithm. "
            "Canonicalization mismatch between simulator and backend."
        )
