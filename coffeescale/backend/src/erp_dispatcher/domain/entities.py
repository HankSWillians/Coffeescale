"""Domain entities for erp_dispatcher.

ADR-003: stdlib only — no boto3, no adapters, no urllib3.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderToDispatch:
    order_id: str
    store_id: str
    device_id: str
    product: str
    quantity_kg: float
    created_at: str


@dataclass(frozen=True)
class ErpResponse:
    success: bool
    status_code: int
    body: str
