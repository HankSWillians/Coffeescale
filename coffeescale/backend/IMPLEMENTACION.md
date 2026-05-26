# IMPLEMENTACION.md — CoffeeScale Backend

## Lo construido

### Estructura completa del monorepo
- `template.yaml` — SAM template con 7 Lambdas, 5 SQS queues + 1 DLQ, 2 tablas DynamoDB, 1 SNS topic, 6 CloudWatch alarms, 1 HTTP API Gateway con 2 endpoints.
- `pyproject.toml` — Poetry + ruff + bandit + import-linter + pytest + moto.
- `.importlinter` — Contratos arquitectónicos Hexagonal para las 4 Lambdas críticas.
- `samconfig.toml` — Configuración por defecto de SAM CLI.
- `.github/workflows/deploy.yml` — Pipeline CI/CD completo (lint → arch → SAST → SCA → tests → build → deploy → smoke).
- `Makefile` — Targets `test`, `lint`, `deploy`, `smoke`, `destroy`, `seed`.
- `README.md` — Documentación completa.
- `scripts/` — `deploy.sh`, `smoke-test.sh`, `seed-parameter-store.sh`.

### Lambda Layer (shared/)
- `logging_config.py` — JSON structured logging con campos obligatorios.
- `metrics.py` — `emit()` para métricas custom a CloudWatch.
- `parameter_store.py` — Cliente SSM con cache TTL configurable (default 60 s).

### 7 Lambdas implementadas

| Lambda | Patrón | Trigger |
|--------|--------|---------|
| `ingestion_handler` | Procedimental | HTTP POST /telemetry |
| `security_validator` | Hexagonal (ADR-003) | SQS telemetry-queue |
| `telemetry_processor` | Hexagonal (ADR-003) | SQS validated-telemetry-queue |
| `order_generator` | Hexagonal (ADR-003) | SQS order-buffer |
| `erp_dispatcher` | Hexagonal (ADR-003), concurrency=1 | SQS erp-dispatch-queue |
| `notification_emitter` | Procedimental | SQS notification-queue |
| `dashboard_api` | N-Tier (ADR-004) | HTTP GET /dashboard/state |

### Tests
- `tests/unit/` — Tests unitarios para las 7 Lambdas (dominio puro + adapters con mocks).
- `tests/integration/test_e2e_flow.py` — 5 pasos del flujo completo con moto.
- `tests/unit/test_security_validator/test_hmac_verifier.py` — Contract test HMAC (Python ↔ Node.js simulator).
- `tests/conftest.py` — Fixtures compartidas (SQS, DynamoDB, credenciales moto).

## Desviaciones del plan original

### 1. Shared Layer — estructura de directorio para SAM
SAM requiere que un Lambda Layer tenga sus archivos Python en `python/` dentro del ContentUri. La configuración del template usa `BuildMethod: python3.12` que lo maneja automáticamente, pero en tests locales el shared module se importa directamente como `src.shared`. Se resuelve con el `PYTHONPATH` apropiado en pytest.

**Workaround aplicado:** `pyproject.toml` configura `src` como root de coverage; los tests importan con prefijo `src.` en tests pero el handler de Lambda importa `shared.` directamente (sin prefijo) porque en Lambda el layer está en el PYTHONPATH.

### 2. Idempotencia en `order_generator` — GSI vs item compuesto
El diseño original no especificaba cómo implementar la deduplicación hora-bucket sin un GSI costoso. **DECISION**: se guarda un atributo `dedup_key = device_id#hour` en el mismo item de la orden y se consulta via GSI `dedup-index`. Esto requiere el GSI definido en `template.yaml`. Alternativa sería DynamoDB conditional write, pero la query es más legible.

### 3. `erp_dispatcher` — SES en notification_emitter
`SESEmailPolicy` requiere que la identidad del remitente esté verificada en SES. En el template se referencia `andinaroasters.co` como identidad. En producción esto debe verificarse manualmente o via Route53 + SES domain verification (fuera del scope del SAM template).

### 4. import-linter — paths de módulos
`import-linter` necesita que los módulos sean importables desde el directorio raíz. En producción cada Lambda tiene su propio deploy package. Para que `lint-imports` funcione localmente, se debe correr desde la raíz del repo con `PYTHONPATH=src` o con el `pyproject.toml` configurando `src` como directorio fuente (ya hecho).

## Deuda técnica conocida

1. **Tests de coverage con src prefix** — Los tests importan como `src.security_validator.handler` pero el código de producción importa como `security_validator.handler`. Esto puede causar doble importación en algunos escenarios. Solución limpia: configurar `PYTHONPATH=src` en `pytest.ini_options`.

2. **DynamoDB dedup-index en tests de integración** — La query al GSI en moto puede comportarse diferente a DynamoDB real con eventualidad en propagación de índices. Añadir un pequeño delay o usar conditional writes como backup.

3. **SES verification en tests** — `notification_emitter` necesita `ses.verify_email_identity` antes de `send_email` en moto. Cubierto en el test de integración pero no en el unit test.

4. **No hay tests de `shared/` explícitos** — `logging_config.py`, `metrics.py`, y `parameter_store.py` están cubiertos indirectamente via tests de las Lambdas. Tests directos agregarían cobertura explícita.

5. **CloudFront para dashboard** — La especificación menciona 30s cache. El `Cache-Control` header está en la respuesta Lambda, pero CloudFront no está en el SAM template (ADR-004 menciona que el dashboard estático va en S3+CloudFront aparte).

6. **AWS Budgets** — Los budgets de $1/$5/$10 no están automatizados (AWS Budgets no es un recurso CloudFormation estándar). Se deben crear manualmente via consola o `aws budgets` CLI.

## Comandos verificados

```bash
# Instalar dependencias
poetry install

# Ejecutar tests
poetry run pytest

# Lint completo
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run lint-imports
poetry run bandit -r src -ll

# Validar template SAM (requiere SAM CLI instalado)
sam validate --lint

# Deploy (requiere credenciales AWS)
make seed    # primera vez
make deploy
make smoke
```

## Próximos pasos sugeridos

1. **Configurar PYTHONPATH en pyproject.toml** para eliminar ambigüedad en imports de tests:
   ```toml
   [tool.pytest.ini_options]
   pythonpath = ["src"]
   ```

2. **Migrar tests a importar sin prefijo `src.`** una vez el PYTHONPATH esté configurado.

3. **Añadir pytest-httpserver** para el mock del ERP en tests de integración (más robusto que `responses` para tests async).

4. **Configurar AWS Budgets** manualmente via consola con alerta a `coffeescale-alerts` SNS topic.

5. **Verificar dominio SES** `andinaroasters.co` en la consola AWS antes del primer deploy a producción.

6. **Implementar X-Ray tracing** completo en `security_validator` y `erp_dispatcher` — el template lo habilita con `Tracing: Active` pero falta instrumentar el código con `aws_xray_sdk`.

7. **Añadir WAF** al API Gateway para rate limiting adicional en el endpoint `/telemetry`.

8. **Dead Letter Queue monitoring** — añadir alarma en `erp-dlq` depth > 0 para alertar cuando órdenes fallen definitivamente.
