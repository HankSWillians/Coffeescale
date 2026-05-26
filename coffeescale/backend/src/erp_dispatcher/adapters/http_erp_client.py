"""HTTP adapter for ErpClient port.

Uses urllib3 (already in the Lambda runtime — no extra dependency).
Timeout: 10 seconds as specified.
ERP URL read from Parameter Store /coffeescale/erp/url.
"""

import json
import os

import urllib3

from erp_dispatcher.domain.entities import ErpResponse, OrderToDispatch
from erp_dispatcher.domain.ports import ErpClient
from shared.logging_config import get_logger
from shared.parameter_store import get_parameter

logger = get_logger(__name__)

ERP_URL_PATH = "/coffeescale/erp/url"
DEFAULT_ERP_URL = os.environ.get("ERP_URL", "https://erp.coffeescale.local/orders")

_http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=5.0, read=10.0))


class HttpErpClient(ErpClient):
    def send(self, order: OrderToDispatch) -> ErpResponse:
        try:
            erp_url = get_parameter(ERP_URL_PATH)
        except Exception:  # noqa: BLE001
            erp_url = DEFAULT_ERP_URL

        body = json.dumps(
            {
                "orderId": order.order_id,
                "storeId": order.store_id,
                "product": order.product,
                "quantityKg": order.quantity_kg,
                "createdAt": order.created_at,
            }
        )

        logger.info("Dispatching to ERP", extra={"order_id": order.order_id, "url": erp_url})

        response = _http.request(
            "POST",
            erp_url,
            body=body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        success = 200 <= response.status < 300
        return ErpResponse(
            success=success,
            status_code=response.status,
            body=response.data.decode("utf-8", errors="replace"),
        )
