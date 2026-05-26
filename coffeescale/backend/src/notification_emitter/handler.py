"""Lambda 6 — notification_emitter.

Consumes SQS notification-queue.  Sends an email to the store manager via SES.

No Hexagonal here: this Lambda has a single adapter (SES) and trivial
procedural logic.  Applying Hexagonal would be over-engineering.
Lambda trivial sin variabilidad esperada en adapters.

ADR reference: ADR-001 (EDA), ADR-002 (Serverless).
"""

import json
import os

import boto3

from shared.logging_config import get_logger
from shared.parameter_store import get_parameter

logger = get_logger(__name__)

_ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
NOTIFICATION_EMAIL_PATH = "/coffeescale/notification/email"
NOTIFICATION_FROM_PATH = "/coffeescale/notification/from"
DEFAULT_FROM = os.environ.get("NOTIFICATION_FROM", "noreply@andinaroasters.co")
DEFAULT_TO = os.environ.get("NOTIFICATION_EMAIL", "gerente@andinaroasters.co")


def _build_email(order: dict) -> tuple[str, str]:
    subject = f"[CoffeeScale] Reposición requerida — {order.get('product', 'Producto desconocido')}"
    body = (
        f"Estimado gerente de tienda {order.get('storeId', '')},\n\n"
        f"Se ha generado automáticamente una orden de reposición:\n\n"
        f"  Producto : {order.get('product')}\n"
        f"  Cantidad : {order.get('quantityKg')} kg\n"
        f"  Orden ID : {order.get('orderId')}\n\n"
        f"Esta orden ya fue enviada al sistema LogisCore.\n\n"
        f"— CoffeeScale Andina Roasters"
    )
    return subject, body


def lambda_handler(event: dict, context: object) -> dict:  # noqa: ARG001
    failures = []

    try:
        from_addr = get_parameter(NOTIFICATION_FROM_PATH)
    except Exception:  # noqa: BLE001
        from_addr = DEFAULT_FROM

    try:
        to_addr = get_parameter(NOTIFICATION_EMAIL_PATH)
    except Exception:  # noqa: BLE001
        to_addr = DEFAULT_TO

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            order = json.loads(record["body"])
            subject, body = _build_email(order)

            _ses.send_email(
                Source=from_addr,
                Destination={"ToAddresses": [to_addr]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                },
            )
            logger.info(
                "Notification email sent",
                extra={"order_id": order.get("orderId"), "to": to_addr},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to send notification",
                extra={"message_id": message_id, "error": str(exc)},
            )
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
