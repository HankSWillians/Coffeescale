"""Parameter Store adapter for ThresholdProvider port.

Reads /coffeescale/thresholds/<product_slug> with 60 s cache.
This covers scenario E4: change thresholds without redeployment.

DECISION: product names are slugified (lowercase, spaces → hyphens) before
building the SSM path, matching the seed-parameter-store.sh convention.
"""

import re

from shared.parameter_store import get_parameter
from telemetry_processor.domain.ports import ThresholdProvider

THRESHOLD_PATH_PREFIX = "/coffeescale/thresholds/"
DEFAULT_THRESHOLD_KG = 5.0  # fallback if product not configured


def _slugify(product: str) -> str:
    """Convert product name to SSM-safe slug."""
    slug = product.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class ParameterStoreThresholdProvider(ThresholdProvider):
    def get_threshold(self, product: str) -> float:
        path = f"{THRESHOLD_PATH_PREFIX}{_slugify(product)}"
        try:
            value = get_parameter(path)
            return float(value)
        except Exception:  # noqa: BLE001
            return DEFAULT_THRESHOLD_KG
