"""N-Tier Layer 2 — Business logic for dashboard_api.

Groups inventory items by store and computes per-sack status.
Produces the same JSON shape as mock-data.js so the static dashboard
works with both mock and real data.

ADR-004: N-Tier (handler → service → repository).
"""

from __future__ import annotations

from dashboard_api import repository


def _sack_status(item: dict) -> str:
    current = item.get("current_kg", 0)
    threshold = item.get("threshold_kg", 5)
    capacity = item.get("capacity_kg", 20)
    ratio = current / capacity if capacity else 0
    if current < threshold:
        return "critical"
    if ratio < 0.3:
        return "warning"
    return "ok"


def get_dashboard_state() -> dict:
    """Return dashboard payload grouped by store.

    Shape:
    {
      "stores": [
        {
          "storeId": "CS-001",
          "sacks": [
            {
              "deviceId": "CS-001-D01",
              "product": "...",
              "currentKg": 14.62,
              "capacityKg": 20,
              "thresholdKg": 5,
              "status": "ok" | "warning" | "critical",
              "timestamp": "..."
            }
          ],
          "status": "ok" | "warning" | "critical"
        }
      ],
      "recentOrders": [ { "orderId": ..., "storeId": ..., ... } ]
    }
    """
    inventory = repository.scan_inventory()
    orders = repository.scan_recent_orders()

    stores: dict[str, dict] = {}
    for item in inventory:
        store_id = item.get("store_id", "unknown")
        if store_id not in stores:
            stores[store_id] = {"storeId": store_id, "sacks": [], "status": "ok"}
        status = _sack_status(item)
        stores[store_id]["sacks"].append(
            {
                "deviceId": item.get("device_id"),
                "product": item.get("product"),
                "currentKg": item.get("current_kg"),
                "capacityKg": item.get("capacity_kg"),
                "thresholdKg": item.get("threshold_kg"),
                "status": status,
                "timestamp": item.get("timestamp"),
            }
        )
        # Store status = worst sack status
        priority = {"critical": 2, "warning": 1, "ok": 0}
        if priority.get(status, 0) > priority.get(stores[store_id]["status"], 0):
            stores[store_id]["status"] = status

    recent_orders = [
        {
            "orderId": o.get("order_id"),
            "storeId": o.get("store_id"),
            "product": o.get("product"),
            "quantityKg": o.get("quantity_kg"),
            "status": o.get("status"),
            "createdAt": o.get("created_at"),
        }
        for o in sorted(orders, key=lambda x: x.get("created_at", ""), reverse=True)
    ]

    return {
        "stores": list(stores.values()),
        "recentOrders": recent_orders,
    }
