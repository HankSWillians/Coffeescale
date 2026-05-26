#!/usr/bin/env bash
# seed-parameter-store.sh — Create initial Parameter Store entries.
# Run once after stack creation, or whenever you need to reset values.
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"

# Replace this with a real secret before running in production!
HMAC_SECRET="${HMAC_SECRET:-CHANGE-ME-IN-PRODUCTION-MIN-32-CHARS}"
ERP_URL="${ERP_URL:-https://erp.coffeescale.local/orders}"
NOTIFICATION_FROM="${NOTIFICATION_FROM:-noreply@andinaroasters.co}"
NOTIFICATION_EMAIL="${NOTIFICATION_EMAIL:-gerente@andinaroasters.co}"

echo "==> Seeding Parameter Store in region $REGION"

aws ssm put-parameter --region "$REGION" --overwrite \
  --name /coffeescale/hmac/secret \
  --type SecureString \
  --value "$HMAC_SECRET"

aws ssm put-parameter --region "$REGION" --overwrite \
  --name /coffeescale/erp/url \
  --type String \
  --value "$ERP_URL"

aws ssm put-parameter --region "$REGION" --overwrite \
  --name /coffeescale/buffer_kg \
  --type String \
  --value "2.0"

aws ssm put-parameter --region "$REGION" --overwrite \
  --name /coffeescale/notification/from \
  --type String \
  --value "$NOTIFICATION_FROM"

aws ssm put-parameter --region "$REGION" --overwrite \
  --name /coffeescale/notification/email \
  --type String \
  --value "$NOTIFICATION_EMAIL"

# Product thresholds (slugified product names)
declare -A THRESHOLDS=(
  ["andina-origen--espresso-blend"]="5.0"
  ["colombia-washed"]="8.0"
  ["ethiopia-natural"]="6.0"
  ["brazil-natural-yellow-bourbon"]="7.0"
  ["costa-rica-honey"]="5.0"
)

for slug in "${!THRESHOLDS[@]}"; do
  aws ssm put-parameter --region "$REGION" --overwrite \
    --name "/coffeescale/thresholds/$slug" \
    --type String \
    --value "${THRESHOLDS[$slug]}"
  echo "  threshold/$slug = ${THRESHOLDS[$slug]} kg"
done

echo "==> Parameter Store seeding complete."
