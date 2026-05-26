"""Custom CloudWatch Metrics helper for CoffeeScale Lambdas.

Mandatory metrics:
  - SecurityFailures (Count)
  - OrdersGenerated (Count)
  - ErpDispatchLatencyMs (Milliseconds)
  - ConfigCacheStale (Count)
"""

import os
from typing import Any

import boto3

_client: Any = None


def _get_client() -> Any:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _client


def emit(
    metric_name: str,
    value: float,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
    namespace: str = "CoffeeScale",
) -> None:
    """Emit a single custom metric to CloudWatch.

    Args:
        metric_name: Name of the metric (e.g. "SecurityFailures").
        value: Numeric value.
        unit: CloudWatch unit string ("Count", "Milliseconds", etc.).
        dimensions: Optional key-value dimension pairs.
        namespace: CloudWatch namespace (default "CoffeeScale").
    """
    dim_list = [{"Name": k, "Value": v} for k, v in (dimensions or {}).items()]
    _get_client().put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Dimensions": dim_list,
            }
        ],
    )
