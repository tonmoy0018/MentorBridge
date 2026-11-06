# MentorBridge

A two-sided mentorship marketplace: students and early-career professionals discover, book and pay for 1:1 sessions with experienced mentors. Administrators verify mentors and keep the marketplace healthy.

> **Project status: the web app and API are integrated and tested end to end. Payments are built but NOT live.**
> - [`frontend/`](frontend/README.md): Next.js app. It uses only real API data.
> - [`backend/`](backend/README.md): Django REST API on PostgreSQL.
> - Verified by automated browser tests against the real stack: register → mentor onboarding → admin approval → search → booking → mentor confirmation → dashboards → cancellation, with conflict and access checks.
> - Free sessions work end to end.
> - Paid sessions: checkout, signed webhooks, commission, refunds and disputes are implemented behind a provider abstraction (Stripe adapter). They're tested against mocked provider responses and Stripe's official mock server, **never against a real provider account**. No provider is chosen yet: that depends on the business's country ([PAYMENTS.md](docs/PAYMENTS.md)). Payments are off by default; nothing fakes a payment, and payouts are manual.
>
> See the [roadmap](docs/DEVELOPMENT_ROADMAP.md) for what's done and what's open.

## Documentation

| Document | Contents |
|---|---|
| [Product requirements](docs/PRODUCT_REQUIREMENTS.md) | Roles, features, booking/payment rules, NFRs, open questions |
| [Architecture](docs/ARCHITECTURE.md) | System design, auth strategy, booking/payment design, security, ADRs, risks |
| [Database schema](docs/DATABASE_SCHEMA.md) | Implemented tables, constraints, indexes |
| [API specification](docs/API_SPECIFICATION.md) | Implemented endpoints, permissions, errors, pagination, booking rules |
| [OpenAPI schema](docs/openapi.yaml) | Generated, machine-readable API contract |
| [Payments](docs/PAYMENTS.md) | Provider research, payment workflow, commission and accounting, webhooks, refunds, configuration, test status |
| [Deployment](docs/DEPLOYMENT.md) | Local setup, production configuration (`deploy/`), deploy steps, smoke tests, backups, rollback |
| [Notifications](docs/NOTIFICATIONS.md) | Transactional emails, de-duplication, privacy, configuration |
| [Development roadmap](docs/DEVELOPMENT_ROADMAP.md) | Milestones, task checklist, blockers, milestone log |

## Tech stack

- **Frontend:** Next.js 16.4 (App Router, Cache Components), React 19, TypeScript 5.9 (strict), Tailwind CSS 4, shadcn/ui (Radix), React Hook Form + Zod 4
- **Backend:** Python 3.13, Django 5.2 LTS, Django REST Framework 3.18, drf-spectacular (OpenAPI), PostgreSQL 17
- **Database:** PostgreSQL 17
- **Testing:** pytest + pytest-django (against PostgreSQL), Vitest + React Testing Library, Playwright
- **Local infrastructure:** Docker Compose (PostgreSQL, backend, frontend, Mailpit)

## Repository layout

```
deploy/      Production compose file, Caddyfile (HTTPS reverse proxy), production env template
backend/     Django project (config/ + apps/: common, users, students, mentors, bookings, payments, reviews, moderation, notifications)
frontend/    Next.js app (src/app, src/components, src/features, src/lib, tests/, e2e/) — see frontend/README.md
docs/        Product, architecture, schema, API and roadmap docs
```

See [ARCHITECTURE.md §3](docs/ARCHITECTURE.md#3-repository-layout-target) for the full tree.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker + Docker Compose | Docker 24+, Compose v2+ | Runs PostgreSQL, the backend and Mailpit |
| Node.js | 20.9+ (24 LTS recommended) | For running the frontend natively |
| pnpm | 9+ (lockfile written with pnpm 12) | `corepack enable` or `npm i -g pnpm` |
| Python | 3.13 *(optional)* | Only if you want to run the backend outside Docker (`brew install python@3.13` or `uv python install 3.13`). macOS's system Python 3.9 is **not** supported by Django 5.2. |

## Run the full stack locally

Requires Docker and Node.js 20.9+ with pnpm.

```bash
make up                  # PostgreSQL (localhost:5433), Mailpit (:8025), Django API (:8000), booking scheduler
make superuser           # create an administrator (role=admin)
make frontend            # Next.js on http://localhost:3000, proxying /api/* to Django
```

Then open:
- http://localhost:3000 for the web app (sign up as a student or mentor),
- http://localhost:8000/api/v1/docs/ for the interactive API docs (dev only),
- http://localhost:8025 for the emails sent in development (verification, bookings, payments),
- http://localhost:8000/django-admin/ for Django admin.

A mentor appears in search only after an admin approves them in **Dashboard → Verification**.

Every default is set in `docker-compose.yml`. Copy `.env.example` to `.env` to override any of them.

### Day-to-day commands

```bash
make test                # backend tests (pytest, separate test database)
make test-stripe-mock    # Stripe adapter requests vs Stripe's official mock server (no real Stripe)
make lint                # ruff + format check + migration drift check
make schema              # regenerate docs/openapi.yaml (fails on schema warnings)
make migrate             # apply migrations
make frontend-test       # frontend lint + typecheck (incl. API contract check) + unit tests
make e2e                 # browser tests against the real stack (Docker; own e2e database)
make gen-api             # regenerate docs/openapi.yaml and the frontend's generated API types
make down                # stop everything (database volume is kept)
```

## Security notes

- Secrets are provided only through environment variables. `.env` is git-ignored, and `.env.example` contains placeholders only.
- Authentication uses Django sessions in HttpOnly cookies with CSRF protection. No tokens are stored in browser storage.
- Payment status is only ever updated from signature-verified provider webhooks or authenticated provider API responses, never from the browser. No card data is stored.
- Development seed data is clearly marked as demo data and must never be loaded in production.

## Contributing workflow

1. Pick a task from [the roadmap](docs/DEVELOPMENT_ROADMAP.md).
2. Branch from `main`.
3. Implement it with tests.
4. Run `make lint test`.
5. Update the docs and the roadmap checklist.
6. Open a PR.
