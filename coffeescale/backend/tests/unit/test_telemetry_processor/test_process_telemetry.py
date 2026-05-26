"""Unit tests for ProcessTelemetry use case and SackState entity."""

from unittest.mock import MagicMock

import pytest

from telemetry_processor.domain.entities import SackState
from telemetry_processor.domain.use_cases import ProcessTelemetry


def _make_packet(weight_kg: float = 14.62, capacity_kg: float = 20.0) -> dict:
    return {
        "deviceId": "CS-001-D01",
        "storeId": "CS-001",
        "product": "Espresso Blend",
        "weightKg": weight_kg,
        "capacityKg": capacity_kg,
        "timestamp": "2026-05-18T14:47:03.142Z",
    }


@pytest.fixture()
def mocks():
    inventory = MagicMock()
    threshold_provider = MagicMock()
    publisher = MagicMock()
    threshold_provider.get_threshold.return_value = 5.0
    use_case = ProcessTelemetry(
        inventory=inventory,
        threshold_provider=threshold_provider,
        order_publisher=publisher,
    )
    return use_case, inventory, threshold_provider, publisher


class TestSackState:
    def test_needs_replenishment_true_when_below_threshold(self):
        state = SackState(
            device_id="D1",
            store_id="S1",
            product="B",
            current_kg=3.0,
            capacity_kg=20.0,
            threshold_kg=5.0,
            timestamp="2026-01-01T00:00:00Z",
        )
        assert state.needs_replenishment is True

    def test_needs_replenishment_false_when_above_threshold(self):
        state = SackState(
            device_id="D1",
            store_id="S1",
            product="B",
            current_kg=10.0,
            capacity_kg=20.0,
            threshold_kg=5.0,
            timestamp="2026-01-01T00:00:00Z",
        )
        assert state.needs_replenishment is False

    def test_needs_replenishment_false_at_exact_threshold(self):
        state = SackState(
            device_id="D1",
            store_id="S1",
            product="B",
            current_kg=5.0,
            capacity_kg=20.0,
            threshold_kg=5.0,
            timestamp="2026-01-01T00:00:00Z",
        )
        assert state.needs_replenishment is False


class TestProcessTelemetry:
    def test_upserts_inventory(self, mocks):
        use_case, inventory, threshold_provider, publisher = mocks
        use_case.execute(_make_packet(weight_kg=10.0))
        inventory.upsert.assert_called_once()

    def test_publishes_order_when_below_threshold(self, mocks):
        use_case, inventory, threshold_provider, publisher = mocks
        use_case.execute(_make_packet(weight_kg=2.0))
        publisher.publish.assert_called_once()

    def test_no_order_when_above_threshold(self, mocks):
        use_case, inventory, threshold_provider, publisher = mocks
        use_case.execute(_make_packet(weight_kg=15.0))
        publisher.publish.assert_not_called()

    def test_returns_sack_state(self, mocks):
        use_case, inventory, threshold_provider, publisher = mocks
        result = use_case.execute(_make_packet(weight_kg=10.0))
        assert isinstance(result, SackState)
        assert result.device_id == "CS-001-D01"

    def test_threshold_queried_with_product(self, mocks):
        use_case, inventory, threshold_provider, publisher = mocks
        use_case.execute(_make_packet())
        threshold_provider.get_threshold.assert_called_with("Espresso Blend")
