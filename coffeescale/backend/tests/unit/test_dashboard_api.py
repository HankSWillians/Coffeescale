"""Unit tests for dashboard_api handler and service layer."""

import json
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("INVENTORY_TABLE", "inventory")
os.environ.setdefault("ORDERS_TABLE", "orders")


@pytest.fixture()
def inventory_items():
    return [
        {
            "device_id": "CS-001-D01",
            "store_id": "CS-001",
            "product": "Espresso Blend",
            "current_kg": 15.0,
            "capacity_kg": 20.0,
            "threshold_kg": 5.0,
            "timestamp": "2026-05-18T14:47:03.142Z",
            "needs_replenishment": False,
        },
        {
            "device_id": "CS-001-D02",
            "store_id": "CS-001",
            "product": "Colombia Washed",
            "current_kg": 3.0,
            "capacity_kg": 50.0,
            "threshold_kg": 5.0,
            "timestamp": "2026-05-18T14:47:03.142Z",
            "needs_replenishment": True,
        },
    ]


@pytest.fixture()
def order_items():
    return [
        {
            "order_id": "ord-1",
            "store_id": "CS-001",
            "product": "Colombia Washed",
            "quantity_kg": 49.0,
            "status": "pending",
            "created_at": "2026-05-18T14:50:00Z",
        }
    ]


def test_handler_returns_200_with_correct_shape(inventory_items, order_items):
    with (
        patch("dashboard_api.repository.scan_inventory", return_value=inventory_items),
        patch("dashboard_api.repository.scan_recent_orders", return_value=order_items),
    ):
        from dashboard_api.handler import lambda_handler

        result = lambda_handler({}, None)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "stores" in body
        assert "recentOrders" in body


def test_service_groups_by_store(inventory_items, order_items):
    with (
        patch("dashboard_api.repository.scan_inventory", return_value=inventory_items),
        patch("dashboard_api.repository.scan_recent_orders", return_value=order_items),
    ):
        from dashboard_api.service import get_dashboard_state

        state = get_dashboard_state()
        stores = state["stores"]
        assert len(stores) == 1
        assert stores[0]["storeId"] == "CS-001"
        assert len(stores[0]["sacks"]) == 2


def test_critical_sack_propagates_to_store_status(inventory_items, order_items):
    with (
        patch("dashboard_api.repository.scan_inventory", return_value=inventory_items),
        patch("dashboard_api.repository.scan_recent_orders", return_value=order_items),
    ):
        from dashboard_api.service import get_dashboard_state

        state = get_dashboard_state()
        store = state["stores"][0]
        # D02 is below threshold → critical → store status should be critical
        assert store["status"] == "critical"


def test_handler_returns_500_on_error():
    with patch("dashboard_api.service.get_dashboard_state", side_effect=Exception("DB error")):
        from dashboard_api.handler import lambda_handler

        result = lambda_handler({}, None)
        assert result["statusCode"] == 500


def test_cors_headers_present(inventory_items, order_items):
    with (
        patch("dashboard_api.repository.scan_inventory", return_value=inventory_items),
        patch("dashboard_api.repository.scan_recent_orders", return_value=order_items),
    ):
        from dashboard_api.handler import lambda_handler

        result = lambda_handler({}, None)
        assert result["headers"]["Access-Control-Allow-Origin"] == "*"
