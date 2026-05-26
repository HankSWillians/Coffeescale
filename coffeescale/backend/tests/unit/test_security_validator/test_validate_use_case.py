"""Unit tests for ValidateTelemetryPacket use case (pure domain)."""

from unittest.mock import MagicMock

import pytest

from security_validator.domain.entities import TelemetryPacket
from security_validator.domain.use_cases import ValidateTelemetryPacket

SECRET = "test-secret"


def _make_packet(sig: str = "abc") -> TelemetryPacket:
    return TelemetryPacket(
        device_id="D1",
        store_id="S1",
        product="Blend",
        weight_kg=10.0,
        capacity_kg=20.0,
        timestamp="2026-01-01T00:00:00Z",
        nonce="n1",
        signature_hex=sig,
    )


@pytest.fixture()
def mocks():
    verifier = MagicMock()
    audit = MagicMock()
    publisher = MagicMock()
    use_case = ValidateTelemetryPacket(verifier=verifier, audit_logger=audit, publisher=publisher)
    return use_case, verifier, audit, publisher


def test_valid_packet_publishes_and_returns_valid(mocks):
    use_case, verifier, audit, publisher = mocks
    verifier.verify.return_value = True
    packet = _make_packet()

    result = use_case.execute(packet, SECRET)

    assert result.is_valid is True
    publisher.publish.assert_called_once_with(packet)
    audit.log_rejection.assert_not_called()


def test_invalid_packet_logs_rejection_and_returns_invalid(mocks):
    use_case, verifier, audit, publisher = mocks
    verifier.verify.return_value = False
    packet = _make_packet()

    result = use_case.execute(packet, SECRET)

    assert result.is_valid is False
    assert result.reason is not None
    audit.log_rejection.assert_called_once()
    publisher.publish.assert_not_called()


def test_validation_result_contains_packet(mocks):
    use_case, verifier, audit, publisher = mocks
    verifier.verify.return_value = True
    packet = _make_packet()

    result = use_case.execute(packet, SECRET)

    assert result.packet is packet
