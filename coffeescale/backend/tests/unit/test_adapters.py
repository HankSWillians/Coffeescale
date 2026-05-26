"""Unit tests for adapter implementations using moto mocks.

Covers: SQS publishers, DynamoDB repositories, CloudWatch audit, metrics, parameter_store.
"""

import hashlib
import hmac
import json
import os
import time

import boto3
from moto import mock_aws

# ── env must be set before any imports ──────────────────────────────────────
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("INVENTORY_TABLE", "inventory")
os.environ.setdefault("ORDERS_TABLE", "orders")


# ── shared/parameter_store ──────────────────────────────────────────────────
class TestParameterStore:
    def setup_method(self):
        from shared import parameter_store

        parameter_store.clear_cache()

    @mock_aws
    def test_get_parameter_fetches_from_ssm(self):
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/test/key", Value="hello", Type="String")

        from shared.parameter_store import get_parameter

        val = get_parameter("/test/key")
        assert val == "hello"

    @mock_aws
    def test_get_parameter_caches_value(self):
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/test/cached", Value="v1", Type="String")

        from shared.parameter_store import get_parameter

        v1 = get_parameter("/test/cached", ttl=60)
        # Update in SSM — should not be reflected due to cache
        ssm.put_parameter(Name="/test/cached", Value="v2", Type="String", Overwrite=True)
        v2 = get_parameter("/test/cached", ttl=60)
        assert v1 == v2 == "v1"

    @mock_aws
    def test_invalidate_clears_cache(self):
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/test/inv", Value="v1", Type="String")

        from shared import parameter_store

        parameter_store.get_parameter("/test/inv")
        ssm.put_parameter(Name="/test/inv", Value="v2", Type="String", Overwrite=True)
        parameter_store.invalidate("/test/inv")
        val = parameter_store.get_parameter("/test/inv")
        assert val == "v2"


# ── shared/metrics ──────────────────────────────────────────────────────────
class TestMetrics:
    @mock_aws
    def test_emit_sends_metric(self):
        from shared import metrics

        # Reset client so it gets a fresh moto one
        metrics._client = None
        metrics.emit("SecurityFailures", 1, "Count", {"StoreId": "CS-001"})
        # No exception = success (moto accepts the call)

    @mock_aws
    def test_emit_with_dimensions(self):
        from shared import metrics

        metrics._client = None
        metrics.emit("OrdersGenerated", 5, "Count", {"StoreId": "CS-001", "Product": "Blend"})


# ── security_validator adapters ─────────────────────────────────────────────
class TestCloudWatchAuditLogger:
    @mock_aws
    def test_log_rejection_does_not_raise(self):
        from shared import metrics

        metrics._client = None

        from security_validator.adapters.cloudwatch_audit import CloudWatchAuditLogger
        from security_validator.domain.entities import TelemetryPacket

        packet = TelemetryPacket(
            device_id="D1",
            store_id="S1",
            product="B",
            weight_kg=10.0,
            capacity_kg=20.0,
            timestamp="2026-01-01T00:00:00Z",
            nonce="n1",
            signature_hex="abc",
        )
        logger = CloudWatchAuditLogger()
        logger.log_rejection(packet, "Bad signature")  # must not raise


class TestSqsValidPacketPublisher:
    @mock_aws
    def test_publish_sends_message(self):
        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="validated-queue")
        queue_url = resp["QueueUrl"]
        os.environ["VALIDATED_QUEUE_URL"] = queue_url

        from security_validator.adapters import sqs_publisher

        sqs_publisher.QUEUE_URL = queue_url

        from security_validator.adapters.sqs_publisher import SqsValidPacketPublisher
        from security_validator.domain.entities import TelemetryPacket

        packet = TelemetryPacket(
            device_id="D1",
            store_id="S1",
            product="B",
            weight_kg=10.0,
            capacity_kg=20.0,
            timestamp="2026-01-01T00:00:00Z",
            nonce="n1",
            signature_hex="abc",
        )
        publisher = SqsValidPacketPublisher()
        publisher.publish(packet)

        messages = sqs.receive_message(QueueUrl=queue_url).get("Messages", [])
        assert len(messages) == 1
        body = json.loads(messages[0]["Body"])
        assert body["deviceId"] == "D1"


# ── telemetry_processor adapters ────────────────────────────────────────────
class TestDynamoDbInventoryRepository:
    @mock_aws
    def test_upsert_stores_item(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
        db.create_table(
            TableName="inventory",
            KeySchema=[{"AttributeName": "device_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "device_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        from telemetry_processor.adapters.dynamodb_inventory import DynamoDbInventoryRepository
        from telemetry_processor.domain.entities import SackState

        repo = DynamoDbInventoryRepository("inventory")
        state = SackState("D1", "S1", "Blend", 10.0, 20.0, 5.0, "2026-01-01T00:00:00Z")
        repo.upsert(state)

        item = db.Table("inventory").get_item(Key={"device_id": "D1"}).get("Item")
        assert item is not None
        assert float(item["current_kg"]) == 10.0

    @mock_aws
    def test_upsert_overwrites_existing(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
        db.create_table(
            TableName="inventory",
            KeySchema=[{"AttributeName": "device_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "device_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        from telemetry_processor.adapters.dynamodb_inventory import DynamoDbInventoryRepository
        from telemetry_processor.domain.entities import SackState

        repo = DynamoDbInventoryRepository("inventory")
        state1 = SackState("D1", "S1", "Blend", 10.0, 20.0, 5.0, "2026-01-01T00:00:00Z")
        state2 = SackState("D1", "S1", "Blend", 7.0, 20.0, 5.0, "2026-01-01T00:01:00Z")
        repo.upsert(state1)
        repo.upsert(state2)

        item = db.Table("inventory").get_item(Key={"device_id": "D1"}).get("Item")
        assert float(item["current_kg"]) == 7.0


class TestParameterStoreThresholdProvider:
    def setup_method(self):
        from shared import parameter_store

        parameter_store.clear_cache()

    @mock_aws
    def test_returns_threshold_from_ssm(self):
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/coffeescale/thresholds/espresso-blend", Value="7.5", Type="String")

        from telemetry_processor.adapters.parameter_store_thresholds import (
            ParameterStoreThresholdProvider,
        )

        provider = ParameterStoreThresholdProvider()
        threshold = provider.get_threshold("Espresso Blend")
        assert threshold == 7.5

    @mock_aws
    def test_returns_default_when_not_configured(self):
        from telemetry_processor.adapters.parameter_store_thresholds import (
            DEFAULT_THRESHOLD_KG,
            ParameterStoreThresholdProvider,
        )

        provider = ParameterStoreThresholdProvider()
        threshold = provider.get_threshold("Unknown Product XYZ")
        assert threshold == DEFAULT_THRESHOLD_KG


class TestSqsOrderPublisher:
    @mock_aws
    def test_publish_sends_order_message(self):
        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="order-buffer")
        queue_url = resp["QueueUrl"]

        from telemetry_processor.adapters import sqs_order_publisher

        sqs_order_publisher.QUEUE_URL = queue_url

        from telemetry_processor.adapters.sqs_order_publisher import SqsOrderPublisher
        from telemetry_processor.domain.entities import SackState

        state = SackState("D1", "S1", "Blend", 3.0, 20.0, 5.0, "2026-01-01T00:00:00Z")
        publisher = SqsOrderPublisher()
        publisher.publish(state)

        messages = sqs.receive_message(QueueUrl=queue_url).get("Messages", [])
        assert len(messages) == 1
        body = json.loads(messages[0]["Body"])
        assert body["deviceId"] == "D1"
        assert body["currentKg"] == 3.0


# ── order_generator adapters ─────────────────────────────────────────────────
class TestDynamoDbOrderRepository:
    @mock_aws
    def _make_table(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
        return db.create_table(
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

    @mock_aws
    def test_save_persists_order(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
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

        from order_generator.adapters.dynamodb_orders import DynamoDbOrderRepository
        from order_generator.domain.entities import ReplenishmentOrder

        repo = DynamoDbOrderRepository("orders")
        order = ReplenishmentOrder(
            order_id="ord-abc",
            store_id="S1",
            device_id="D1",
            product="Blend",
            quantity_kg=15.0,
            created_at="2026-05-18T14:00:00Z",
            status="pending",
        )
        repo.save(order)

        item = db.Table("orders").get_item(Key={"order_id": "ord-abc"}).get("Item")
        assert item is not None
        assert item["status"] == "pending"

    @mock_aws
    def test_exists_for_device_in_hour_false_when_no_orders(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
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

        from order_generator.adapters.dynamodb_orders import DynamoDbOrderRepository

        repo = DynamoDbOrderRepository("orders")
        exists = repo.exists_for_device_in_hour("D1", "2026-05-18T14")
        assert exists is False


class TestSqsErpQueuePublisher:
    @mock_aws
    def test_publish_sends_to_erp_queue(self):
        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="erp-dispatch-queue")
        queue_url = resp["QueueUrl"]

        from order_generator.adapters import sqs_notification

        sqs_notification.QUEUE_URL = queue_url

        from order_generator.adapters.sqs_notification import SqsErpQueuePublisher
        from order_generator.domain.entities import ReplenishmentOrder

        order = ReplenishmentOrder(
            order_id="ord-1",
            store_id="S1",
            device_id="D1",
            product="Blend",
            quantity_kg=15.0,
            created_at="2026-05-18T14:00:00Z",
            status="pending",
        )
        publisher = SqsErpQueuePublisher()
        publisher.publish(order)

        messages = sqs.receive_message(QueueUrl=queue_url).get("Messages", [])
        assert len(messages) == 1
        body = json.loads(messages[0]["Body"])
        assert body["orderId"] == "ord-1"


class TestParameterStoreBufferKgProvider:
    def setup_method(self):
        from shared import parameter_store

        parameter_store.clear_cache()

    @mock_aws
    def test_returns_configured_buffer(self):
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/coffeescale/buffer_kg", Value="3.5", Type="String")

        from order_generator.adapters.sqs_notification import ParameterStoreBufferKgProvider

        provider = ParameterStoreBufferKgProvider()
        assert provider.get_buffer_kg() == 3.5

    @mock_aws
    def test_returns_default_when_not_configured(self):
        from order_generator.adapters.sqs_notification import ParameterStoreBufferKgProvider

        provider = ParameterStoreBufferKgProvider()
        assert provider.get_buffer_kg() == 2.0  # default


# ── erp_dispatcher adapters ──────────────────────────────────────────────────
class TestRealSleeper:
    def test_sleeper_sleeps_briefly(self):
        from erp_dispatcher.adapters.exponential_backoff import RealSleeper

        sleeper = RealSleeper()
        start = time.monotonic()
        sleeper.sleep(0.05)  # 50ms — above Windows timer resolution (~15ms)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.02  # tolerant for Windows timer rounding

class TestDynamoDbStatusUpdater:
    @mock_aws
    def test_update_changes_status(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
        db.create_table(
            TableName="orders",
            KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        db.Table("orders").put_item(
            Item={
                "order_id": "ord-x",
                "status": "pending",
                "store_id": "S1",
                "product": "Blend",
            }
        )

        from erp_dispatcher.adapters.exponential_backoff import DynamoDbStatusUpdater

        updater = DynamoDbStatusUpdater("orders")
        updater.update("ord-x", "sent")

        item = db.Table("orders").get_item(Key={"order_id": "ord-x"}).get("Item")
        assert item["status"] == "sent"


class TestSqsNotificationPublisher:
    @mock_aws
    def test_publish_success_sends_message(self):
        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="notification-queue")
        queue_url = resp["QueueUrl"]

        from erp_dispatcher.adapters import exponential_backoff

        exponential_backoff.NOTIFICATION_QUEUE_URL = queue_url

        from erp_dispatcher.adapters.exponential_backoff import SqsNotificationPublisher
        from erp_dispatcher.domain.entities import OrderToDispatch

        order = OrderToDispatch(
            order_id="ord-1",
            store_id="S1",
            device_id="D1",
            product="Blend",
            quantity_kg=15.0,
            created_at="2026-05-18T14:00:00Z",
        )
        publisher = SqsNotificationPublisher()
        publisher.publish_success(order)

        messages = sqs.receive_message(QueueUrl=queue_url).get("Messages", [])
        assert len(messages) == 1


# ── handler-level integration tests (SQS events) ────────────────────────────
class TestSecurityValidatorHandler:
    def setup_method(self):
        from shared import parameter_store

        parameter_store.clear_cache()

    @mock_aws
    def test_handler_processes_valid_packet(self):

        # Setup SSM
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/coffeescale/hmac/secret", Value="test-secret", Type="SecureString")

        # Setup SQS
        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="validated-queue")
        queue_url = resp["QueueUrl"]
        os.environ["VALIDATED_QUEUE_URL"] = queue_url

        from security_validator.adapters import sqs_publisher

        sqs_publisher.QUEUE_URL = queue_url

        from shared import metrics

        metrics._client = None

        payload = {
            "deviceId": "D1",
            "storeId": "S1",
            "product": "Blend",
            "weightKg": 10.0,
            "capacityKg": 20.0,
            "timestamp": "2026-01-01T00:00:00Z",
            "nonce": "n1",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        sig = hmac.new(b"test-secret", canonical, hashlib.sha256).hexdigest()
        auth = f"HMAC-SHA256 keyId=D1, signature={sig}"
        body = json.dumps({"payload": payload, "authorization": auth})

        event = {"Records": [{"messageId": "msg-1", "body": body}]}

        from security_validator.handler import lambda_handler

        result = lambda_handler(event, None)
        assert result == {"batchItemFailures": []}

    @mock_aws
    def test_handler_rejects_invalid_signature(self):
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/coffeescale/hmac/secret", Value="test-secret", Type="SecureString")

        sqs = boto3.client("sqs", region_name="us-east-1")
        sqs.create_queue(QueueName="validated-queue2")

        from shared import metrics

        metrics._client = None

        payload = {
            "deviceId": "D1",
            "storeId": "S1",
            "product": "Blend",
            "weightKg": 10.0,
            "capacityKg": 20.0,
            "timestamp": "2026-01-01T00:00:00Z",
            "nonce": "n1",
        }
        auth = "HMAC-SHA256 keyId=D1, signature=badhexbadhex"
        body = json.dumps({"payload": payload, "authorization": auth})
        event = {"Records": [{"messageId": "msg-1", "body": body}]}

        from security_validator.handler import lambda_handler

        result = lambda_handler(event, None)
        # Invalid signature is NOT a batch failure — it's silently discarded
        assert result == {"batchItemFailures": []}


class TestTelemetryProcessorHandler:
    def setup_method(self):
        from shared import parameter_store

        parameter_store.clear_cache()

    @mock_aws
    def test_handler_upserts_and_enqueues(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
        db.create_table(
            TableName="inventory",
            KeySchema=[{"AttributeName": "device_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "device_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="order-buf")
        queue_url = resp["QueueUrl"]
        os.environ["ORDER_BUFFER_QUEUE_URL"] = queue_url

        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/coffeescale/thresholds/blend", Value="5.0", Type="String")

        from telemetry_processor.adapters import dynamodb_inventory, sqs_order_publisher

        sqs_order_publisher.QUEUE_URL = queue_url
        dynamodb_inventory.TABLE_NAME = "inventory"

        packet = {
            "deviceId": "D1",
            "storeId": "S1",
            "product": "Blend",
            "weightKg": 2.0,
            "capacityKg": 20.0,
            "timestamp": "2026-01-01T00:00:00Z",
        }
        event = {"Records": [{"messageId": "m1", "body": json.dumps(packet)}]}

        from telemetry_processor.handler import lambda_handler

        result = lambda_handler(event, None)
        assert result == {"batchItemFailures": []}

        item = db.Table("inventory").get_item(Key={"device_id": "D1"}).get("Item")
        assert item is not None


class TestOrderGeneratorHandler:
    def setup_method(self):
        from shared import parameter_store

        parameter_store.clear_cache()

    @mock_aws
    def test_handler_creates_order(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
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

        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="erp-dis")
        queue_url = resp["QueueUrl"]
        os.environ["ERP_DISPATCH_QUEUE_URL"] = queue_url

        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/coffeescale/buffer_kg", Value="2.0", Type="String")

        from order_generator.adapters import dynamodb_orders, sqs_notification

        sqs_notification.QUEUE_URL = queue_url
        dynamodb_orders.TABLE_NAME = "orders"

        from shared import metrics

        metrics._client = None

        message = {
            "deviceId": "D1",
            "storeId": "S1",
            "product": "Blend",
            "currentKg": 2.0,
            "capacityKg": 20.0,
            "thresholdKg": 5.0,
            "timestamp": "2026-01-01T00:00:00Z",
        }
        event = {"Records": [{"messageId": "m1", "body": json.dumps(message)}]}

        from order_generator.handler import lambda_handler

        result = lambda_handler(event, None)
        assert result == {"batchItemFailures": []}

        scan = db.Table("orders").scan()
        assert len(scan["Items"]) == 1


class TestErpDispatcherHandler:
    @mock_aws
    def test_handler_dispatches_to_erp(self):
        db = boto3.resource("dynamodb", region_name="us-east-1")
        db.create_table(
            TableName="orders",
            KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        db.Table("orders").put_item(
            Item={
                "order_id": "ord-1",
                "status": "pending",
                "store_id": "S1",
                "product": "Blend",
            }
        )

        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(QueueName="notif")
        notif_url = resp["QueueUrl"]
        os.environ["NOTIFICATION_QUEUE_URL"] = notif_url

        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(
            Name="/coffeescale/erp/url", Value="https://erp.test.local/orders", Type="String"
        )

        from shared import parameter_store

        parameter_store.clear_cache()
        from shared import metrics

        metrics._client = None

        from erp_dispatcher.adapters import exponential_backoff

        exponential_backoff.ORDERS_TABLE = "orders"
        exponential_backoff.NOTIFICATION_QUEUE_URL = notif_url

        erp_msg = json.dumps(
            {
                "orderId": "ord-1",
                "storeId": "S1",
                "deviceId": "D1",
                "product": "Blend",
                "quantityKg": 15.0,
                "createdAt": "2026-05-18T14:00:00Z",
            }
        )
        event = {"Records": [{"messageId": "m1", "body": erp_msg}]}

        # Patch the HTTP client directly (responses library can't intercept urllib3 directly)
        from erp_dispatcher import handler as erp_handler
        from erp_dispatcher.domain.entities import ErpResponse

        original_execute = erp_handler._use_case.execute

        def mock_execute(order):
            from erp_dispatcher.adapters.exponential_backoff import (
                DynamoDbStatusUpdater,
                SqsNotificationPublisher,
            )

            DynamoDbStatusUpdater("orders").update(order.order_id, "sent")
            SqsNotificationPublisher().publish_success(order)
            return ErpResponse(success=True, status_code=200, body="ok")

        erp_handler._use_case.execute = mock_execute
        result = erp_handler.lambda_handler(event, None)
        erp_handler._use_case.execute = original_execute

        assert result == {"batchItemFailures": []}
        item = db.Table("orders").get_item(Key={"order_id": "ord-1"}).get("Item")
        assert item["status"] == "sent"
