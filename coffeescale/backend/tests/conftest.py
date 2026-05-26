"""Shared pytest fixtures for CoffeeScale test suite."""

import hashlib
import hmac
import json
import os

import boto3
import pytest
from moto import mock_aws

# ── Environment defaults so imports don't explode without real AWS ───────────
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("INVENTORY_TABLE", "inventory")
os.environ.setdefault("ORDERS_TABLE", "orders")
os.environ.setdefault(
    "TELEMETRY_QUEUE_URL", "http://sqs.us-east-1.localhost/000000000000/coffeescale-telemetry-queue"
)
os.environ.setdefault(
    "VALIDATED_QUEUE_URL",
    "http://sqs.us-east-1.localhost/000000000000/coffeescale-validated-telemetry-queue",
)
os.environ.setdefault(
    "ORDER_BUFFER_QUEUE_URL", "http://sqs.us-east-1.localhost/000000000000/coffeescale-order-buffer"
)
os.environ.setdefault(
    "ERP_DISPATCH_QUEUE_URL",
    "http://sqs.us-east-1.localhost/000000000000/coffeescale-erp-dispatch-queue",
)
os.environ.setdefault(
    "NOTIFICATION_QUEUE_URL",
    "http://sqs.us-east-1.localhost/000000000000/coffeescale-notification-queue",
)

TEST_HMAC_SECRET = "test-secret-12345"
TEST_DEVICE_ID = "CS-001-D01"
TEST_STORE_ID = "CS-001"
TEST_PRODUCT = "Andina Origen — Espresso Blend"


def make_signed_payload(
    device_id: str = TEST_DEVICE_ID,
    store_id: str = TEST_STORE_ID,
    product: str = TEST_PRODUCT,
    weight_kg: float = 14.62,
    capacity_kg: float = 20.0,
    timestamp: str = "2026-05-18T14:47:03.142Z",
    nonce: str = "k9x2p4q1m8",
    secret: str = TEST_HMAC_SECRET,
) -> dict:
    """Build a valid telemetry payload with a correct HMAC signature."""
    data = {
        "deviceId": device_id,
        "storeId": store_id,
        "product": product,
        "weightKg": weight_kg,
        "capacityKg": capacity_kg,
        "timestamp": timestamp,
        "nonce": nonce,
    }
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return {**data, "signature": sig}


@pytest.fixture()
def sample_payload():
    return make_signed_payload()


@pytest.fixture()
def hmac_secret():
    return TEST_HMAC_SECRET


@pytest.fixture()
def aws_credentials():
    """Mocked AWS credentials for moto."""
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"


@pytest.fixture()
def sqs_queues(aws_credentials):
    with mock_aws():
        client = boto3.client("sqs", region_name="us-east-1")
        queues = {}
        for name in [
            "coffeescale-telemetry-queue",
            "coffeescale-validated-telemetry-queue",
            "coffeescale-order-buffer",
            "coffeescale-erp-dispatch-queue",
            "coffeescale-notification-queue",
        ]:
            resp = client.create_queue(QueueName=name)
            queues[name] = resp["QueueUrl"]
            env_key = name.upper().replace("-", "_").replace("COFFEESCALE_", "") + "_URL"
            os.environ[env_key] = resp["QueueUrl"]
        # Also set the specific env vars used by handlers
        os.environ["TELEMETRY_QUEUE_URL"] = queues["coffeescale-telemetry-queue"]
        os.environ["VALIDATED_QUEUE_URL"] = queues["coffeescale-validated-telemetry-queue"]
        os.environ["ORDER_BUFFER_QUEUE_URL"] = queues["coffeescale-order-buffer"]
        os.environ["ERP_DISPATCH_QUEUE_URL"] = queues["coffeescale-erp-dispatch-queue"]
        os.environ["NOTIFICATION_QUEUE_URL"] = queues["coffeescale-notification-queue"]
        yield queues


@pytest.fixture()
def dynamodb_tables(aws_credentials):
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        # inventory table
        inventory = db.create_table(
            TableName="inventory",
            KeySchema=[{"AttributeName": "device_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "device_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        # orders table with GSI
        orders = db.create_table(
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
        yield {"inventory": inventory, "orders": orders}
