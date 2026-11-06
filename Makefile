# Common development commands. The backend runs in Docker (Python 3.13); the frontend runs natively.
COMPOSE := docker compose
RUN := $(COMPOSE) run --rm backend

.PHONY: up down logs migrate makemigrations superuser shell test test-stripe-mock lint format schema gen-api check frontend frontend-test e2e

up:            ## Start PostgreSQL, Mailpit, the API (:8000) and the booking scheduler
	$(COMPOSE) up -d --build

down:          ## Stop the stack (data is kept in the pgdata volume)
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f backend scheduler

migrate:
	$(RUN) python manage.py migrate

makemigrations:
	$(RUN) python manage.py makemigrations

superuser:     ## Create an administrator account
	$(COMPOSE) run --rm -it backend python manage.py createsuperuser

shell:
	$(COMPOSE) run --rm -it backend python manage.py shell

test:          ## Backend tests (pytest, separate test database)
	$(RUN) pytest

test-stripe-mock: ## Check the Stripe adapter's requests against stripe-mock (no real Stripe calls)
	docker run --rm -d --name mentorbridge-stripe-mock --network mentorbridge_default stripe/stripe-mock:v0.206.0
	$(COMPOSE) run --rm -e STRIPE_MOCK_URL=http://mentorbridge-stripe-mock:12111 backend \
		pytest -p no:cacheprovider tests/test_stripe_mock.py; \
		status=$$?; docker stop mentorbridge-stripe-mock >/dev/null; exit $$status

lint:          ## Backend lint + format check + migration drift check
	$(RUN) sh -c "ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run"

format:
	$(RUN) sh -c "ruff format . && ruff check --fix ."

schema:        ## Regenerate docs/openapi.yaml (fails on schema warnings)
	$(RUN) python manage.py spectacular --validate --fail-on-warn --file openapi.yaml
	mv backend/openapi.yaml docs/openapi.yaml

gen-api: schema   ## Regenerate the OpenAPI schema and the frontend's generated types
	cd frontend && pnpm gen:api

check: lint test gen-api

frontend:      ## Next.js dev server against the local API
	cd frontend && INTERNAL_API_URL=http://localhost:8000 pnpm dev

frontend-test: ## Lint, typecheck (incl. API contract check) and unit tests
	cd frontend && pnpm lint && pnpm typecheck && pnpm test

e2e:           ## Browser tests against the real stack (starts db, mailpit, api-e2e on :8001, web on :3200)
	cd frontend && pnpm test:e2e
