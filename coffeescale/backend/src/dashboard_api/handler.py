"""Lambda 7 — dashboard_api (entry point).

GET /dashboard/state — returns current state of all stores and recent orders.
Read-only DynamoDB access.

N-Tier Architecture (ADR-004): handler → service → repository.
No Hexagonal — documented choice: this is a simple read model with no
domain rules or port variability expected.

CORS headers included for the static HTML dashboard served from S3.
"""

import json

from dashboard_api import service
from shared.logging_config import get_logger

logger = get_logger(__name__)

_CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "max-age=30",  # CloudFront 30-second cache per spec
}


def lambda_handler(event: dict, context: object) -> dict:  # noqa: ARG001
    try:
        data = service.get_dashboard_state()
        logger.info("Dashboard state retrieved", extra={"store_count": len(data.get("stores", []))})
        return {
            "statusCode": 200,
            "headers": _CORS_HEADERS,
            "body": json.dumps(data),
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to retrieve dashboard state", extra={"error": str(exc)})
        return {
            "statusCode": 500,
            "headers": _CORS_HEADERS,
            "body": json.dumps({"error": "Internal server error"}),
        }
