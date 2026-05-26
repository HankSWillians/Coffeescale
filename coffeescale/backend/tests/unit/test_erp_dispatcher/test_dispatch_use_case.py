"""Unit tests for DispatchOrderToErp use case and exponential backoff policy."""

from unittest.mock import MagicMock, call

import pytest

from erp_dispatcher.domain.entities import ErpResponse, OrderToDispatch
from erp_dispatcher.domain.use_cases import BASE_DELAY, MAX_ATTEMPTS, DispatchOrderToErp


def _make_order() -> OrderToDispatch:
    return OrderToDispatch(
        order_id="ord-123",
        store_id="CS-001",
        device_id="CS-001-D01",
        product="Espresso Blend",
        quantity_kg=18.0,
        created_at="2026-05-18T14:00:00Z",
    )


@pytest.fixture()
def mocks():
    erp_client = MagicMock()
    status_updater = MagicMock()
    notifier = MagicMock()
    sleeper = MagicMock()
    use_case = DispatchOrderToErp(
        erp_client=erp_client,
        status_updater=status_updater,
        notification_publisher=notifier,
        sleeper=sleeper,
    )
    return use_case, erp_client, status_updater, notifier, sleeper


def test_successful_dispatch_on_first_attempt(mocks):
    use_case, client, updater, notifier, sleeper = mocks
    client.send.return_value = ErpResponse(success=True, status_code=200, body="ok")

    result = use_case.execute(_make_order())

    assert result.success is True
    client.send.assert_called_once()
    updater.update.assert_called_once_with("ord-123", "sent")
    notifier.publish_success.assert_called_once()
    sleeper.sleep.assert_not_called()


def test_retries_on_failure_and_succeeds(mocks):
    use_case, client, updater, notifier, sleeper = mocks
    fail = ErpResponse(success=False, status_code=500, body="err")
    ok = ErpResponse(success=True, status_code=200, body="ok")
    client.send.side_effect = [fail, fail, ok]

    result = use_case.execute(_make_order())

    assert result.success is True
    assert client.send.call_count == 3
    # sleep called between attempts: 0.5s, 1s (2 failures before success on attempt 3)
    assert sleeper.sleep.call_count == 2
    assert sleeper.sleep.call_args_list[0] == call(BASE_DELAY)
    assert sleeper.sleep.call_args_list[1] == call(BASE_DELAY * 2)


def test_raises_after_max_attempts_and_marks_failed(mocks):
    use_case, client, updater, notifier, sleeper = mocks
    client.send.return_value = ErpResponse(success=False, status_code=503, body="unavail")

    with pytest.raises(RuntimeError, match="ERP dispatch failed"):
        use_case.execute(_make_order())

    assert client.send.call_count == MAX_ATTEMPTS
    updater.update.assert_called_with("ord-123", "failed")
    notifier.publish_success.assert_not_called()


def test_exception_from_client_is_treated_as_failure(mocks):
    use_case, client, updater, notifier, sleeper = mocks
    client.send.side_effect = ConnectionError("timeout")

    with pytest.raises(RuntimeError):
        use_case.execute(_make_order())

    assert client.send.call_count == MAX_ATTEMPTS


def test_backoff_delays_are_exponential(mocks):
    use_case, client, updater, notifier, sleeper = mocks
    client.send.return_value = ErpResponse(success=False, status_code=500, body="err")

    with pytest.raises(RuntimeError):
        use_case.execute(_make_order())

    delays = [c.args[0] for c in sleeper.sleep.call_args_list]
    # Delays should be: 0.5, 1.0, 2.0, 4.0 (4 sleeps between 5 attempts)
    assert len(delays) == MAX_ATTEMPTS - 1
    for i, d in enumerate(delays):
        assert d == pytest.approx(BASE_DELAY * (2**i))
