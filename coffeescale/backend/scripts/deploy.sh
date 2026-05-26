#!/usr/bin/env bash
# deploy.sh — Build and deploy the CoffeeScale backend to AWS
set -euo pipefail

STACK_NAME="${STACK_NAME:-coffeescale-prod}"
ALERT_EMAIL="${ALERT_EMAIL:-engineering@andinaroasters.co}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

echo "==> Building SAM application..."
sam build --use-container

echo "==> Deploying stack: $STACK_NAME to $REGION"
sam deploy \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --parameter-overrides "AlertEmail=$ALERT_EMAIL"

echo "==> Deploy complete."
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs" \
  --output table
