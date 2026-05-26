"""Domain entities for order_generator.

ADR-003: stdlib only — no boto3, no adapters.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReplenishmentOrder:
    order_id: str
    store_id: str
    device_id: str
    product: str
    quantity_kg: float
    created_at: str
    status: str  # "pending" | "sent" | "confirmed" | "failed"
