# CoffeeScale Backend

IoT inventory replenishment system for Andina Roasters. Digital scales
under each coffee sack report weight every 60 seconds; when a sack drops
below its configured threshold the system auto-generates a purchase order
to the LogisCore ERP.

## Architecture overview

```
IoT Device
    │ HTTPS POST /telemetry (HMAC-SHA256 signed)
    ▼
API Gateway ──► ingestion_handler
                    │ SQS
                    ▼
            security_validator (Hexagonal, HMAC verify)
                    │ SQS
                    ▼
            telemetry_processor (Hexagonal, DynamoDB upsert + threshold check)
                    │ SQS (if weight < threshold)
                    ▼
            order_generator (Hexagonal, creates ReplenishmentOrder)
                    │ SQS
                    ▼
            erp_dispatcher (Hexagonal, ReservedConcurrency=1, HTTP→LogisCore)
                    │ SQS
                    ▼
            notification_emitter (SES email)

Dashboard: GET /dashboard/state ──► dashboard_api (N-Tier, read-only DynamoDB)
```

**ADRs implemented:** ADR-001 (EDA/SQS), ADR-002 (Serverless/Lambda), ADR-003 (Hexagonal in 4 core Lambdas), ADR-004 (N-Tier for dashboard).

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.12 |
| Poetry | latest |
| AWS CLI | v2 |
| SAM CLI | latest |
| AWS account | Free Tier |

## Local setup

```bash
git clone <repo>
cd coffeescale-backend
cp .env.example .env          # fill in HMAC_SECRET, ERP_URL, NOTIFICATION_EMAIL
poetry install
```

## Common commands

| Command | Action |
|---------|--------|
| `make test` | Run tests + coverage (≥80% required) |
| `make lint` | Lint + architecture contracts + SAST |
| `make deploy` | SAM build + deploy to prod |
| `make smoke` | Post-deploy smoke test |
| `make destroy` | Delete the CloudFormation stack |
| `make seed` | Seed Parameter Store with initial values |

## Deploy to AWS

### One-time OIDC setup (recommended — no long-lived keys)

1. Create an OIDC provider in IAM for `token.actions.githubusercontent.com`.
2. Create an IAM role `CoffeeScaleDeployRole` with the OIDC provider as trusted entity
   and the minimum deploy permissions (CloudFormation, Lambda, SQS, DynamoDB, SSM, SNS, S3, IAM).
3. Add the role ARN as a GitHub secret `AWS_DEPLOY_ROLE_ARN`.
4. Add `ALERT_EMAIL`, `HMAC_SECRET`, and `SEMGREP_APP_TOKEN` as GitHub secrets.

### Manual deploy

```bash
# 1. Configure AWS credentials
aws configure  # or use aws sso login

# 2. Seed Parameter Store (first time only)
HMAC_SECRET="your-strong-secret" make seed

# 3. Deploy
make deploy

# 4. Smoke test
make smoke
```

## End-to-end test with the Node.js simulator

```bash
# 1. Deploy the backend
make deploy

# 2. Get the telemetry endpoint
ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name coffeescale-prod \
  --query "Stacks[0].Outputs[?OutputKey=='TelemetryEndpoint'].OutputValue" \
  --output text)

# 3. Get the HMAC secret
HMAC_SECRET=$(aws ssm get-parameter \
  --name /coffeescale/hmac/secret \
  --with-decryption \
  --query Parameter.Value \
  --output text)

# 4. Run the simulator (adjust path as needed)
cd ../simulator
HMAC_SECRET="$HMAC_SECRET" \
node simulator.js --endpoint "$ENDPOINT" --stores 5 --rate 5 --duration 60
```

## CloudWatch monitoring

Six alarms are configured automatically:

| Alarm | Condition |
|-------|-----------|
| `HighErrorRate` | Lambda errors > 10 / 5 min |
| `ERPConcurrencyBreach` | erp_dispatcher concurrency > 1 |
| `QueueBacklog` | telemetry-queue depth > 5 000 / 10 min |
| `SecurityFailures` | HMAC failures > 100 / min |
| `DynamoThrottles` | DynamoDB throttles > 0 |
| `IngestLatencyP99` | ingestion_handler p99 > 5 000 ms |

All alarm notifications go to the SNS topic → email specified in `AlertEmail`.

## Project structure highlights

```
src/
  shared/           Lambda Layer — logging, metrics, Parameter Store cache
  ingestion_handler/  Lambda 1 — procedural, HTTP ingestion
  security_validator/ Lambda 2 — Hexagonal, HMAC validation
  telemetry_processor/ Lambda 3 — Hexagonal, inventory + threshold
  order_generator/    Lambda 4 — Hexagonal, order creation
  erp_dispatcher/     Lambda 5 — Hexagonal, ERP HTTP dispatch (concurrency=1)
  notification_emitter/ Lambda 6 — procedural, SES email
  dashboard_api/      Lambda 7 — N-Tier, read-only dashboard
tests/
  unit/             Pure domain tests (no AWS calls)
  integration/      Full flow with moto AWS mocks
```

## ADR traceability

| ADR | Where enforced |
|-----|---------------|
| ADR-001 (EDA) | SQS queues in template.yaml, all inter-Lambda comms |
| ADR-002 (Serverless) | 7 Lambda functions, API Gateway, DynamoDB PAY_PER_REQUEST |
| ADR-003 (Hexagonal) | domain/ + adapters/ in 4 Lambdas, validated by import-linter |
| ADR-004 (N-Tier dashboard) | dashboard_api handler→service→repository |

## Security notes

- HMAC-SHA256 protects every telemetry packet end-to-end.
- Parameter Store SecureString for the HMAC secret (never in env vars or code).
- IAM roles are minimal per Lambda (SQS read/write, DynamoDB targeted tables only).
- OIDC for CI/CD — no long-lived access keys.
- Bandit + Semgrep SAST run on every commit.
- pip-audit SCA on every commit.
