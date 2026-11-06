# MentorBridge — Backend

Django 5.2 LTS · Django REST Framework 3.18 · PostgreSQL 17 · Python 3.13 · drf-spectacular (OpenAPI).

## Run it

```bash
# from the repository root
make up                 # PostgreSQL (host port 5433), Mailpit (:8025), API (:8000), scheduler
make superuser          # create an admin account (role=admin, staff)
open http://localhost:8000/api/v1/docs/     # Swagger UI (dev only)
open http://localhost:8025                  # emails sent in development
```

`make up` runs `migrate` and `createcachetable` on start. Defaults live in `docker-compose.yml`; override them in a root `.env` (see `.env.example`). The frontend talks to this API through its `/api/*` proxy: `make frontend`.

| Command | What it does |
|---|---|
| `make test` | pytest on a separate test database (`test_mentorbridge`, created and destroyed by pytest-django) |
| `make lint` | `ruff check`, `ruff format --check`, `makemigrations --check` |
| `make schema` | Regenerate and validate `docs/openapi.yaml` (fails on warnings) |
| `make migrate` / `make makemigrations` | Database migrations |
| `make test-stripe-mock` | Runs `tests/test_stripe_mock.py` against Stripe's official mock server (request shapes only; no real Stripe) |
| `make e2e` | Browser tests: starts the `api-e2e` service (`config.settings.e2e`, database `mentorbridge_e2e`, port 8001). The database is created by `scripts/ensure_database.py` if missing and is never reset, and the test admin by `manage.py ensure_admin` |
| `docker compose run --rm backend python manage.py expire_bookings` | Expire lapsed holds/requests. The `scheduler` service runs this, `send_session_reminders` and `send_notifications` (email retries) every minute |

Local Python 3.9 (macOS system) can't run Django 5.2, so everything runs in the container. To run natively, install Python 3.13, `pip install -r requirements-dev.txt`, and point `DATABASE_URL` at `postgres://mentorbridge:mentorbridge@localhost:5433/mentorbridge`.

## Layout

```
config/settings/{base,dev,test,prod}.py   prod refuses to start with insecure settings
apps/
  common/      base models, AuditLogEntry, error envelope, pagination, permissions, throttles, request IDs, health/stats
  users/       custom User (email login, role, timezone), auth endpoints, tokens, admin user management
  taxonomy/    Category, Profession, Skill, Language (+ seed migration)
  mentors/     MentorProfile, MentorSkill, MentorExperience, MentorService, AvailabilityRule/Exception,
               VerificationRequest, slot engine (slots.py), selectors, services
  students/    StudentProfile, SavedMentor, CareerGoal
  bookings/    Booking (+ exclusion constraints), BookingEvent, state machine + services, booking emails,
               expire_bookings, send_session_reminders
  payments/    Payment, Refund, WebhookEvent, Payout; provider abstraction + Stripe adapter (providers/),
               commission maths, webhook processing, refunds/disputes, earnings selectors (docs/PAYMENTS.md)
  notifications/ EmailNotification (dedupe keys), templated email delivery + retries (docs/NOTIFICATIONS.md)
  reviews/     Review (+ rating aggregation)
  moderation/  Report
tests/         pytest suite (Postgres-backed)
```

Each app follows `models → selectors (reads) → services (writes, transactions) → serializers → views`. Views stay thin, and every state change goes through a service.

## Security notes

- Session-cookie auth with CSRF enforced on every unsafe request, including anonymous login, register and reset (`EnforceCSRFMixin`). Unauthenticated requests get 401; wrong role gets 403; other people's objects get 404.
- Roles are checked server-side (`apps/common/permissions.py`). Admin endpoints require `role=admin` **and** `is_staff`.
- Mentors can't change `verification_status`, ratings or payment data. These fields aren't in any writable serializer, and payment and booking rows are read-only in Django admin.
- Paid sessions can't be booked while `PAYMENT_PROVIDER` is empty (the default). An unknown provider or malformed keys refuse to start. `GET /api/v1/config/` exposes `payments_enabled` and `payments_livemode`.
- Payment state changes only in `apps/payments/services.py`: from signature-verified, de-duplicated webhooks, or from authenticated provider API responses (capture/refund). No API sets it; the browser's checkout return changes nothing. No card data is stored. **Live payments have never been tested** (docs/PAYMENTS.md §9).
- Transactional emails are queued in the transaction and sent after commit (`apps.notifications`), de-duplicated by key and retried. Mail-server failures never fail the request, and logs carry ids only.
- Passwords use Django's hashers and validators. Reset and verification tokens are HMAC-based, single-use and time-limited. Reset requests never reveal whether an account exists.
- Rate limits use the database cache, so they hold across worker processes.

API details: [docs/API_SPECIFICATION.md](../docs/API_SPECIFICATION.md). Schema: [docs/DATABASE_SCHEMA.md](../docs/DATABASE_SCHEMA.md).
