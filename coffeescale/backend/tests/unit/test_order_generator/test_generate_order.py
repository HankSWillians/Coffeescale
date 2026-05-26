"""Unit tests for GenerateOrder use case."""

from unittest.mock import MagicMock

import pytest

from order_generator.domain.use_cases import GenerateOrder


def _make_message(capacity_kg: float = 20.0, current_kg: float = 2.0) -> dict:
    return {
        "deviceId": "CS-001-D01",
        "storeId": "CS-001",
        "product": "Espresso Blend",
        "capacityKg": capacity_kg,
        "currentKg": current_kg,
        "thresholdKg": 5.0,
        "timestamp": "2026-05-18T14:47:03.142Z",
    }


@pytest.fixture()
def mocks():
    repo = MagicMock()
    publisher = MagicMock()
    buffer_provider = MagicMock()
    repo.exists_for_device_in_hour.return_value = False
    buffer_provider.get_buffer_kg.return_value = 2.0
    use_case = GenerateOrder(repository=repo, publisher=publisher, buffer_provider=buffer_provider)
    return use_case, repo, publisher, buffer_provider


def test_creates_order_with_correct_quantity(mocks):
    use_case, repo, publisher, buffer = mocks
    order = use_case.execute(_make_message(capacity_kg=20.0, current_kg=2.0))
    # quantity = 20 - 2 + 2 (buffer) = 20
    assert order is not None
    assert order.quantity_kg == 20.0


def test_skips_when_duplicate_within_hour(mocks):
    use_case, repo, publisher, buffer = mocks
    repo.exists_for_device_in_hour.return_value = True
    result = use_case.execute(_make_message())
    assert result is None
    repo.save.assert_not_called()
    publisher.publish.assert_not_called()


def test_saves_order_with_pending_status(mocks):
    use_case, repo, publisher, buffer = mocks
    order = use_case.execute(_make_message())
    assert order is not None
    assert order.status == "pending"
    repo.save.assert_called_once()


def test_publishes_to_erp_queue(mocks):
    use_case, repo, publisher, buffer = mocks
    use_case.execute(_make_message())
    publisher.publish.assert_called_once()


def test_order_has_uuid_id(mocks):
    use_case, repo, publisher, buffer = mocks
    order = use_case.execute(_make_message())
    assert order is not None
    import uuid

    uuid.UUID(order.order_id)  # raises if not valid UUID


def test_quantity_never_negative(mocks):
    use_case, repo, publisher, buffer = mocks
    # current > capacity (sensor anomaly) — quantity should be 0 or buffer only
    order = use_case.execute(_make_message(capacity_kg=10.0, current_kg=15.0))
    assert order is not None
    assert order.quantity_kg >= 0
