"""Unit tests for notification_emitter handler."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("NOTIFICATION_FROM", "noreply@andinaroasters.co")
os.environ.setdefault("NOTIFICATION_EMAIL", "gerente@andinaroasters.co")


def _make_event(order: dict | None = None) -> dict:
    default_order = {
        "orderId": "ord-123",
        "storeId": "CS-001",
        "product": "Espresso Blend",
        "quantityKg": 18.0,
    }
    return {"Records": [{"messageId": "msg-1", "body": json.dumps(order or default_order)}]}


@pytest.fixture(autouse=True)
def mock_ses():
    from notification_emitter import handler as notif_module

    original = notif_module._ses
    ses_instance = MagicMock()
    ses_instance.send_email.return_value = {"MessageId": "ses-msg-id"}
    notif_module._ses = ses_instance
    yield ses_instance
    notif_module._ses = original


@pytest.fixture(autouse=True)
def mock_param_store():
    with patch("notification_emitter.handler.get_parameter", side_effect=Exception("no param")):
        yield


def test_sends_email_for_valid_order(mock_ses):
    from notification_emitter.handler import lambda_handler

    result = lambda_handler(_make_event(), None)
    assert result == {"batchItemFailures": []}
    mock_ses.send_email.assert_called_once()


def test_email_contains_product_in_subject(mock_ses):
    from notification_emitter.handler import lambda_handler

    lambda_handler(_make_event(), None)
    call_args = mock_ses.send_email.call_args
    subject = call_args.kwargs["Message"]["Subject"]["Data"]
    assert "Espresso Blend" in subject


def test_returns_batch_failure_on_ses_error(mock_ses):
    mock_ses.send_email.side_effect = Exception("SES error")
    from notification_emitter.handler import lambda_handler

    result = lambda_handler(_make_event(), None)
    assert len(result["batchItemFailures"]) == 1
    assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-1"
