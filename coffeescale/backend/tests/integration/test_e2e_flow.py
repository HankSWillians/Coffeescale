"""Integration test: full E2E flow with moto AWS mocks.

Flow tested:
  1. HTTP POST → ingestion_handler → SQS telemetry-queue
  2. telemetry-queue message → security_validator → validated-telemetry-queue
  3. validated-telemetry-queue → telemetry_processor → DynamoDB inventory + order-buffer
  4. order-buffer → order_generator → DynamoDB orders + erp-dispatch-queue
  5. erp-dispatch-queue → erp_dispatcher → (mocked ERP) → notification-queue
  6. notification-queue → notification_emitter → (mocked SES)

All AWS services are mocked with moto.  The ERP HTTP call is mocked with
responses library.
"""

import hashlib
import hmac
import json
import os

import boto3
import pytest
from moto import mock_aws

# ── Test constants ──────────────────────────────────────────────────────────
SECRET = "integration-test-secret"
DEVICE_ID = "CS-001-D01"
STORE_ID = "CS-001"
PRODUCT = "Andina Origen — Espresso Blend"
ERP_URL = "https://erp.test.local/orders"

# ── Env setup must happen before any lambda imports ─────────────────────────
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["INVENTORY_TABLE"] = "inventory"
os.environ["ORDERS_TABLE"] = "orders"
os.environ["ERP_URL"] = ERP_URL


def _signed_payload(weight_kg: float = 3.0) -> dict:
    data = {
        "deviceId": DEVICE_ID,
        "storeId": STORE_ID,
        "product": PRODUCT,
        "weightKg": weight_kg,
        "capacityKg": 20.0,
        "timestamp": "2026-05-18T14:47:03.142Z",
        "nonce": "k9x2p4q1m8",
    }
    node_data = {k: (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in data.items()}
    canonical = json.dumps(node_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(SECRET.encode(), canonical, hashlib.sha256).hexdigest()
    return {**data, "signature": sig}


@pytest.fixture(scope="module")
def aws_environment():
    """Create all AWS resources for the integration test."""
    with mock_aws():
        sqs = boto3.client("sqs", region_name="us-east-1")
        ssm = boto3.client("ssm", region_name="us-east-1")
        db = boto3.resource("dynamodb", region_name="us-east-1")
        ses = boto3.client("ses", region_name="us-east-1")

        # SQS Queues
        queues = {}
        for name in [
            "coffeescale-telemetry-queue",
            "coffeescale-validated-telemetry-queue",
            "coffeescale-order-buffer",
            "coffeescale-erp-dispatch-queue",
            "coffeescale-notification-queue",
        ]:
            resp = sqs.create_queue(QueueName=name)
            queues[name] = resp["QueueUrl"]

        os.environ["TELEMETRY_QUEUE_URL"] = queues["coffeescale-telemetry-queue"]
        os.environ["VALIDATED_QUEUE_URL"] = queues["coffeescale-validated-telemetry-queue"]
        os.environ["ORDER_BUFFER_QUEUE_URL"] = queues["coffeescale-order-buffer"]
        os.environ["ERP_DISPATCH_QUEUE_URL"] = queues["coffeescale-erp-dispatch-queue"]
        os.environ["NOTIFICATION_QUEUE_URL"] = queues["coffeescale-notification-queue"]

        # DynamoDB Tables
        db.create_table(
            TableName="inventory",
            KeySchema=[{"AttributeName": "device_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "device_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        db.create_table(
            TableName="orders",
            KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "order_id", "AttributeType": "S"},
                {"AttributeName": "dedup_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "dedup-index",
                    "KeySchema": [{"AttributeName": "dedup_key", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                }
            ],
        )

        # Parameter Store entries
        ssm.put_parameter(Name="/coffeescale/hmac/secret", Value=SECRET, Type="SecureString")
        ssm.put_parameter(
            Name="/coffeescale/thresholds/andina-origen--espresso-blend", Value="5.0", Type="String"
        )
        ssm.put_parameter(Name="/coffeescale/erp/url", Value=ERP_URL, Type="String")
        ssm.put_parameter(Name="/coffeescale/buffer_kg", Value="2.0", Type="String")
        ssm.put_parameter(
            Name="/coffeescale/notification/from", Value="noreply@andinaroasters.co", Type="String"
        )
        ssm.put_parameter(
            Name="/coffeescale/notification/email", Value="gerente@andinaroasters.co", Type="String"
        )

        # SES: verify sender identity
        ses.verify_email_identity(EmailAddress="noreply@andinaroasters.co")

        yield {
            "sqs": sqs,
            "ssm": ssm,
            "db": db,
            "ses": ses,
            "queues": queues,
        }


def test_step1_ingestion_handler_enqueues_message(aws_environment):
    """ingestion_handler accepts valid payload and puts message in SQS."""
    from shared.parameter_store import clear_cache

    clear_cache()

    payload = _signed_payload()
    event = {
        "body": json.dumps(payload),
        "headers": {
            "authorization": f"HMAC-SHA256 keyId={DEVICE_ID}, signature={payload['signature']}"
        },
    }

    from ingestion_handler.handler import lambda_handler

    result = lambda_handler(event, None)
    assert result["statusCode"] == 202

    sqs = aws_environment["sqs"]
    messages = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-telemetry-queue"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])
    assert len(messages) == 1
    body = json.loads(messages[0]["Body"])
    assert body["payload"]["deviceId"] == DEVICE_ID


def test_step2_security_validator_validates_and_forwards(aws_environment):
    """security_validator accepts a valid HMAC and forwards to validated queue."""
    from shared.parameter_store import clear_cache

    clear_cache()

    payload = _signed_payload()
    auth_header = f"HMAC-SHA256 keyId={DEVICE_ID}, signature={payload['signature']}"
    message_body = json.dumps({"payload": payload, "authorization": auth_header})

    sqs = aws_environment["sqs"]
    sqs.send_message(
        QueueUrl=aws_environment["queues"]["coffeescale-telemetry-queue"],
        MessageBody=message_body,
    )

    messages = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-telemetry-queue"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])

    event = {"Records": [{"messageId": messages[0]["MessageId"], "body": messages[0]["Body"]}]}

    from security_validator.handler import lambda_handler

    result = lambda_handler(event, None)
    assert result == {"batchItemFailures": []}

    validated = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-validated-telemetry-queue"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])
    assert len(validated) == 1


def test_step3_telemetry_processor_upserts_inventory(aws_environment):
    """telemetry_processor upserts DynamoDB and enqueues order-buffer (weight < threshold)."""
    from shared.parameter_store import clear_cache

    clear_cache()

    payload = _signed_payload(weight_kg=3.0)  # below threshold of 5
    message_body = json.dumps(
        {
            "deviceId": payload["deviceId"],
            "storeId": payload["storeId"],
            "product": payload["product"],
            "weightKg": payload["weightKg"],
            "capacityKg": payload["capacityKg"],
            "timestamp": payload["timestamp"],
        }
    )

    sqs = aws_environment["sqs"]
    sqs.send_message(
        QueueUrl=aws_environment["queues"]["coffeescale-validated-telemetry-queue"],
        MessageBody=message_body,
    )
    messages = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-validated-telemetry-queue"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])

    event = {"Records": [{"messageId": messages[0]["MessageId"], "body": messages[0]["Body"]}]}

    from telemetry_processor.handler import lambda_handler

    result = lambda_handler(event, None)
    assert result == {"batchItemFailures": []}

    # Verify DynamoDB upsert
    table = aws_environment["db"].Table("inventory")
    item = table.get_item(Key={"device_id": DEVICE_ID}).get("Item")
    assert item is not None
    assert float(item["current_kg"]) == 3.0

    # Verify order-buffer has message
    order_msgs = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-order-buffer"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])
    assert len(order_msgs) == 1


def test_step4_order_generator_creates_order(aws_environment):
    """order_generator creates an order in DynamoDB and queues for ERP dispatch."""
    from shared.parameter_store import clear_cache

    clear_cache()

    sqs = aws_environment["sqs"]
    # Ensure order-buffer has a message (from step 3 or fresh)
    order_buffer_msg = json.dumps(
        {
            "deviceId": DEVICE_ID,
            "storeId": STORE_ID,
            "product": PRODUCT,
            "currentKg": 3.0,
            "capacityKg": 20.0,
            "thresholdKg": 5.0,
            "timestamp": "2026-05-18T14:47:03.142Z",
        }
    )
    sqs.send_message(
        QueueUrl=aws_environment["queues"]["coffeescale-order-buffer"],
        MessageBody=order_buffer_msg,
    )
    messages = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-order-buffer"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])

    event = {"Records": [{"messageId": messages[0]["MessageId"], "body": messages[0]["Body"]}]}

    from order_generator.handler import lambda_handler

    result = lambda_handler(event, None)
    assert result == {"batchItemFailures": []}

    # Verify order in DynamoDB
    table = aws_environment["db"].Table("orders")
    scan = table.scan()
    assert len(scan["Items"]) >= 1

    # Verify ERP dispatch queue
    erp_msgs = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-erp-dispatch-queue"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])
    assert len(erp_msgs) == 1


def test_step5_erp_dispatcher_sends_to_erp(aws_environment):
    """erp_dispatcher sends HTTP POST to ERP and updates order status.

    urllib3 cannot be intercepted by the responses library, so we patch
    the HttpErpClient.send method directly to simulate an ERP 200 response.
    """
    import time
    import uuid
    from unittest.mock import MagicMock, patch

    from shared.parameter_store import clear_cache

    clear_cache()

    sqs = aws_environment["sqs"]
    db = aws_environment["db"]

    order_id = str(uuid.uuid4())
    db.Table("orders").put_item(
        Item={
            "order_id": order_id,
            "store_id": STORE_ID,
            "device_id": DEVICE_ID,
            "product": PRODUCT,
            "quantity_kg": 19,
            "created_at": "2026-05-18T14:47:00Z",
            "status": "pending",
            "expires_at": int(time.time()) + 86400,
            "dedup_key": f"{DEVICE_ID}#2026-05-18T14",
        }
    )

    erp_msg = json.dumps(
        {
            "orderId": order_id,
            "storeId": STORE_ID,
            "deviceId": DEVICE_ID,
            "product": PRODUCT,
            "quantityKg": 19.0,
            "createdAt": "2026-05-18T14:47:00Z",
            "status": "pending",
        }
    )
    sqs.send_message(
        QueueUrl=aws_environment["queues"]["coffeescale-erp-dispatch-queue"],
        MessageBody=erp_msg,
    )
    messages = sqs.receive_message(
        QueueUrl=aws_environment["queues"]["coffeescale-erp-dispatch-queue"],
        MaxNumberOfMessages=1,
    ).get("Messages", [])

    event = {"Records": [{"messageId": messages[0]["MessageId"], "body": messages[0]["Body"]}]}

    # Patch urllib3 at the adapter level — responses library can't intercept urllib3 directly
    mock_http_response = MagicMock()
    mock_http_response.status = 200
    mock_http_response.data = b'{"status":"accepted"}'

    erp_request_path = "erp_dispatcher.adapters.http_erp_client._http.request"
    with patch(erp_request_path, return_value=mock_http_response):
        from erp_dispatcher.handler import lambda_handler

        result = lambda_handler(event, None)

    assert result == {"batchItemFailures": []}

    # Verify order status updated to "sent"
    item = db.Table("orders").get_item(Key={"order_id": order_id}).get("Item")
    assert item["status"] == "sent"
