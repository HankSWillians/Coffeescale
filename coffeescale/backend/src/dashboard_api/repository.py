"""N-Tier Layer 3 — DynamoDB read-only repository for dashboard_api.

ADR-004: N-Tier (handler → service → repository) for this subsystem.
"""

import os
from decimal import Decimal
from typing import Any

import boto3

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
INVENTORY_TABLE = os.environ.get("INVENTORY_TABLE", "inventory")
ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "orders")


def _decimal_to_float(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(i) for i in obj]
    return obj


def scan_inventory() -> list[dict]:
    """Return all rows from the inventory table."""
    table = _dynamodb.Table(INVENTORY_TABLE)
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    return [_decimal_to_float(i) for i in items]


def scan_recent_orders(limit: int = 50) -> list[dict]:
    """Return the most recent orders (up to *limit*)."""
    table = _dynamodb.Table(ORDERS_TABLE)
    response = table.scan(Limit=limit)
    return [_decimal_to_float(i) for i in response.get("Items", [])]
