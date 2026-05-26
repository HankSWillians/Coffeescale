#!/usr/bin/env bash
# smoke-test.sh — Post-deploy smoke test: sends a signed telemetry packet
# and verifies HTTP 202 response.
set -euo pipefail

STACK_NAME="${STACK_NAME:-coffeescale-prod}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# 1. Get the endpoint from CloudFormation outputs
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='TelemetryEndpoint'].OutputValue" \
  --output text)

if [[ -z "$ENDPOINT" ]]; then
  echo "ERROR: Could not retrieve TelemetryEndpoint from stack $STACK_NAME"
  exit 1
fi
echo "==> Endpoint: $ENDPOINT"

# 2. Get HMAC secret (from env or Parameter Store)
if [[ -z "${HMAC_SECRET:-}" ]]; then
  HMAC_SECRET=$(aws ssm get-parameter \
    --name /coffeescale/hmac/secret \
    --with-decryption \
    --region "$REGION" \
    --query Parameter.Value \
    --output text)
fi

# 3. Build signed payload using Python (already in PATH from Poetry env)
NONCE="smoke$(date +%s)"
TIMESTAMP=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")
DEVICE_ID="CS-SMOKE-D01"

PAYLOAD=$(python3 - <<PYEOF
import hashlib, hmac, json, sys

secret = "$HMAC_SECRET"
data = {
    "deviceId": "$DEVICE_ID",
    "storeId": "CS-SMOKE",
    "product": "Smoke Test Blend",
    "weightKg": 15.0,
    "capacityKg": 20.0,
    "timestamp": "$TIMESTAMP",
    "nonce": "$NONCE",
}
canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
sig = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
print(json.dumps({**data, "signature": sig}))
PYEOF
)

SIGNATURE=$(echo "$PAYLOAD" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['signature'])")

# 4. Send request
echo "==> Sending smoke test request..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: HMAC-SHA256 keyId=$DEVICE_ID, signature=$SIGNATURE" \
  -d "$PAYLOAD")

echo "==> HTTP Status: $HTTP_STATUS"
if [[ "$HTTP_STATUS" != "202" ]]; then
  echo "FAIL: Expected 202, got $HTTP_STATUS"
  exit 1
fi
echo "PASS: Smoke test succeeded."
