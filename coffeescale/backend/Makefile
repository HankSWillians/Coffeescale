.PHONY: install test lint deploy smoke destroy seed

install:
	poetry install --no-interaction

test:
	poetry run pytest

lint:
	poetry run ruff check src tests
	poetry run ruff format --check src tests
	poetry run lint-imports
	poetry run bandit -r src -ll
	poetry run pip-audit

deploy:
	./scripts/deploy.sh

smoke:
	./scripts/smoke-test.sh

destroy:
	sam delete --stack-name $${STACK_NAME:-coffeescale-prod} --no-prompts

seed:
	./scripts/seed-parameter-store.sh
