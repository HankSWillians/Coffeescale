"""Unit tests for ingestion_handler."""

import json
import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TELEMETRY_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/000/test-queue")


@pytest.fixture(autouse=True)
def mock_sqs():
    # Patch the module-level _sqs directly because it's initialized at import time
    from ingestion_handler import handler as ingestion_module

    original = ingestion_module._sqs
    mock_sqs_instance = MagicMock()
    mock_sqs_instance.send_message.return_value = {"MessageId": "test-msg-id"}
    ingestion_module._sqs = mock_sqs_instance
    yield mock_sqs_instance
    ingestion_module._sqs = original


def _make_event(body: dict | None = None, headers: dict | None = None) -> dict:
    default_headers = {"authorization": "HMAC-SHA256 keyId=CS-001-D01, signature=abc123"}
    default_body = {
        "deviceId": "CS-001-D01",
        "storeId": "CS-001",
        "product": "Espresso Blend",
        "weightKg": 14.62,
        "capacityKg": 20,
        "timestamp": "2026-05-18T14:47:03.142Z",
        "nonce": "k9x2p4q1m8",
    }
    return {
        "body": json.dumps(body if body is not None else default_body),
        "headers": headers if headers is not None else default_headers,
    }


def test_valid_payload_returns_202(mock_sqs):
    from ingestion_handler.handler import lambda_handler

    response = lambda_handler(_make_event(), None)
    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["status"] == "accepted"
    assert "requestId" in body


def test_missing_auth_header_returns_401(mock_sqs):
    from ingestion_handler.handler import lambda_handler

    event = _make_event(headers={})
    response = lambda_handler(event, None)
    assert response["statusCode"] == 401


def test_invalid_json_returns_400(mock_sqs):
    from ingestion_handler.handler import lambda_handler

    event = _make_event()
    event["body"] = "not-json{"
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["code"] == "INVALID_PAYLOAD"


def test_missing_fields_returns_400(mock_sqs):
    from ingestion_handler.handler import lambda_handler

    payload = {"deviceId": "CS-001-D01"}  # missing most fields
    response = lambda_handler(_make_event(body=payload), None)
    assert response["statusCode"] == 400


def test_invalid_weight_type_returns_400(mock_sqs):
    from ingestion_handler.handler import lambda_handler

    payload = {
        "deviceId": "CS-001-D01",
        "storeId": "CS-001",
        "product": "Blend",
        "weightKg": "not-a-number",
        "capacityKg": 20,
        "timestamp": "2026-01-01T00:00:00Z",
        "nonce": "abc",
    }
    response = lambda_handler(_make_event(body=payload), None)
    assert response["statusCode"] == 400


def test_enqueues_to_sqs_on_success(mock_sqs):
    from ingestion_handler.handler import lambda_handler

    lambda_handler(_make_event(), None)
    mock_sqs.send_message.assert_called_once()
    assert mock_sqs.send_message.call_args is not None
