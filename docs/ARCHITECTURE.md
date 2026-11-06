# MentorBridge — Architecture

Status: Draft v0.1 (Milestone 0)
Last updated: 2026-10-27

## 1. System overview

```
                         ┌──────────────────────────────────────────────┐
  Browser ──HTTPS──►     │  Single public origin (e.g. mentorbridge.app) │
                         │                                              │
                         │   /            ─►  Next.js (SSR + RSC)        │
                         │   /api/*       ─►  Django + DRF (JSON API)    │
                         │   /django-admin─►  Django admin (staff only)  │
                         └───────────┬──────────────────┬───────────────┘
                                     │ server-side fetch │
                                     │ (forwards cookie) ▼
                                     │            ┌──────────────┐
                                     └──────────► │  Django API  │──► PostgreSQL 17
                                                  └──────┬───────┘
                                                         │
                                  Stripe (Checkout, webhooks) · Email provider (SMTP/API)
```

- **Frontend:** Next.js (App Router), TypeScript in strict mode, Tailwind CSS, shadcn/ui. It renders pages and calls the API. It never touches the database.
- **Backend:** Django + Django REST Framework. It owns all business rules, permissions, persistence and third-party integrations.
- **Database:** PostgreSQL. It's the only source of truth. Constraints in the database back up the application-level rules.
- **Same-origin by design:** in production a reverse proxy (Caddy/nginx or the hosting platform's router) serves both apps from one domain. In development, Next.js `rewrites` proxy `/api/*` to Django. Because of this, auth cookies are first-party, CORS isn't needed for the browser, and CSRF works the standard Django way.

## 2. Technology choices

| Layer | Choice | Version target | Notes |
|---|---|---|---|
| Runtime (BE) | Python | 3.13.18 (`python:3.13.18-slim-bookworm`) | System Python here is 3.9; the backend runs in Docker |
| Web framework | Django | 5.2.18 LTS | LTS until April 2028. Django 6.1 is newer, but DRF-ecosystem packages (drf-spectacular, django-cors-headers, pytest-django) don't yet declare support for it |
| API | Django REST Framework | 3.18.x | |
| API schema | drf-spectacular | 0.30.x | OpenAPI 3 schema → generated TypeScript types |
| DB driver | psycopg | 3.x (`psycopg[binary]` in dev, `psycopg[c]` in prod) | |
| Config | django-environ | 0.14.0 | 12-factor env vars |
| Other BE | django-countries 9.1, Pillow 13 (avatar validation), tzdata, gunicorn 26, django-cors-headers 4.9 | | |
| Database | PostgreSQL | 17.11 | Uses `btree_gist` and exclusion constraints |
| Payments | Stripe (`stripe` Python SDK) | latest stable at Milestone 4 | Behind a provider interface |
| Runtime (FE) | Node.js | 24 LTS+ (26 installed locally) | |
| Framework | Next.js | 16.4.3 | App Router, React Server Components, Cache Components (PPR) enabled |
| UI | React 19.3, Tailwind CSS 4.3, shadcn/ui (Radix base, `radix-nova` style) | | |
| Forms | React Hook Form + Zod 4 | | |
| Language | TypeScript | 5.9.3 | TS 7 (native port) is pinned out until Next.js tooling supports it |
| Package manager | pnpm | | Lockfile committed |
| BE tests | pytest + pytest-django + factory_boy | | Tests run against real PostgreSQL |
| FE tests | Vitest + React Testing Library + MSW | | |
| E2E | Playwright | 1.6x | Runs against the full Docker Compose stack |
| Lint/format | ruff (BE), ESLint + Prettier (FE) | | |

Exact versions are pinned in lockfiles when each package is first installed. Nothing is assumed installed.

## 3. Repository layout

```
MentorBridge/
├── README.md
├── docker-compose.yml          # db, mailpit, backend, scheduler (frontend runs natively)
├── .env.example                # all config keys, no real secrets
├── Makefile                    # common dev commands
├── docs/
│   ├── PRODUCT_REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_SPECIFICATION.md
│   └── DEVELOPMENT_ROADMAP.md
├── backend/
│   ├── Dockerfile
│   ├── requirements*.txt       # pinned deps; pyproject.toml holds ruff + pytest config
│   ├── manage.py
│   ├── config/
│   │   ├── settings/{base,dev,test,prod}.py
│   │   ├── urls.py             # /api/v1/ router, /django-admin/
│   │   ├── asgi.py, wsgi.py
│   └── apps/
│       ├── common/             # base models, AuditLogEntry, permissions, pagination, errors, throttles, health/stats
│       ├── users/              # custom User, auth endpoints, tokens, admin user management
│       ├── taxonomy/           # Category ("industries"), Profession, Skill, Language + seed migration
│       ├── students/           # StudentProfile, SavedMentor, CareerGoal
│       ├── mentors/            # MentorProfile, MentorSkill, experience, services, availability, verification, slots.py
│       ├── bookings/           # Booking (exclusion constraints), BookingEvent, state machine, expire_bookings
│       ├── payments/           # Payment, Payout (records only), earnings selectors
│       ├── reviews/            # Review + rating aggregation
│       └── moderation/         # Report
│   ├── tests/                  # pytest suite (PostgreSQL-backed)
│   Each app: models.py · selectors.py (reads) · services.py (writes) · serializers.py · views.py · urls.py · admin.py
└── frontend/                     # see frontend/README.md
    ├── package.json, next.config.ts, tsconfig.json, components.json (shadcn)
    ├── src/
    │   ├── app/
    │   │   ├── (site)/          # /, /mentors, /mentors/[id]   (navbar + footer)
    │   │   ├── (auth)/          # /login, /signup, /signup/{student,mentor}, /forgot-password, /reset-password
    │   │   └── dashboard/       # /dashboard → role redirect; student/, mentor/, admin/ (role-gated layouts)
    │   ├── components/
    │   │   ├── ui/              # shadcn primitives (owned code)
    │   │   └── layout/ mentors/ bookings/ forms/ feedback/ common/ dashboard/ auth/
    │   ├── features/            # dashboard screens: student/, mentor/, admin/, account/
    │   ├── hooks/               # useApiQuery, useApiErrorHandler
    │   ├── lib/
    │   │   ├── api/             # types.ts, errors.ts, http.ts, contract.ts, live.ts, transports
    │   │   ├── data/            # client.ts (browser) and server.ts (RSC: getServerApi, getCurrentUser, requireRole)
    │   │   └── validation/      # shared Zod schemas
    │   └── proxy.ts             # Next 16 request proxy (formerly middleware): coarse auth redirects
    ├── tests/                   # Vitest unit/component tests
    └── e2e/                     # Playwright specs
```

## 4. Backend design

### 4.1 Layering inside each Django app

| Layer | Responsibility | Rules |
|---|---|---|
| `models.py` | Schema, constraints, simple derived properties | No cross-app workflows |
| `selectors.py` | Read queries (filtering, annotation, `select_related`) | Return querysets/objects. No writes |
| `services.py` | Business operations (`create_booking`, `accept_booking`, `record_webhook_event`) | Own transactions, enforce state machines, emit audit events |
| `serializers.py` | Input validation and output shape | No business side effects in `save()` beyond calling a service |
| `views.py` | HTTP: auth, permissions, throttles, calls service/selector | Thin |
| `permissions.py` | DRF permission classes (`IsStudent`, `IsMentor`, `IsAdminRole`, object-level ownership) | |

Cross-app calls go through the other app's `services`/`selectors`, never through its views.

### 4.2 Authentication strategy — Django sessions over same-origin cookies

**Decision:** use Django's session authentication with a CSRF token, not JWTs.

- `POST /api/v1/auth/login/` validates credentials, calls `django.contrib.auth.login()`, and rotates the session key.
- The `sessionid` cookie is `HttpOnly`, `Secure` (prod), `SameSite=Lax`, with a 2-week lifetime configurable via env.
- The `csrftoken` cookie is readable by JS. The frontend sends it as `X-CSRFToken` on every unsafe request. DRF's `SessionAuthentication` enforces CSRF.
- `GET /api/v1/auth/csrf/` makes sure the CSRF cookie is set (`ensure_csrf_cookie`).
- **Server Components** call Django directly at `INTERNAL_API_URL` and forward the incoming `Cookie` header. They never persist tokens.
- `proxy.ts` only checks whether a session cookie exists, to redirect anonymous users quickly. **Authorization is always decided by Django.**

Why: there are no tokens in `localStorage`, nothing for XSS to steal, server-side revocation works (logout, suspend), and it uses Django's mature auth, password hashing (PBKDF2 → Argon2 optional) and password-reset flows. The trade-off is that a native mobile client would later need token auth. DRF can add that alongside without changing the web app.

### 4.3 Roles and permissions
- `User.role ∈ {student, mentor, admin}` is the authoritative role for API permissions. Admins also get `is_staff=True` for Django admin access.
- Default DRF permission is `IsAuthenticated`. Public endpoints opt out explicitly with `AllowAny`.
- Object-level checks always filter querysets by the requesting user (`Booking.objects.for_user(user)`), so a guessed ID returns **404, not 403**. This avoids leaking whether the resource exists.
- Suspended users (`is_active=False`) can't authenticate. Their existing sessions are invalidated on suspension.

### 4.4 Booking engine and conflict prevention
- **Slot generation (read path):** `mentors/slots.py` is a pure function with no database access.
  - It expands weekly `AvailabilityRule`s per date in each rule's IANA zone, so DST is handled with `zoneinfo`.
  - It adds `available` and subtracts `unavailable` `AvailabilityException`s.
  - It offers starts every `SLOT_STEP_MINUTES` (30) whose whole range `[start, end + buffer)` avoids existing active bookings.
  - It applies min-notice and the booking horizon, and returns UTC starts.
  - `mentors/selectors.py` feeds it, loading bookings and exceptions one day either side of the window so slots near the edge are judged correctly.
- **Creation (write path):** `services.create_booking()` runs in `transaction.atomic()`:
  1. Locks the mentor row (`select_for_update`) to serialize concurrent bookings for one mentor.
  2. Expires that mentor's (and student's) stale holds and unanswered requests.
  3. Revalidates that the requested start is a currently valid slot.
  4. Inserts the booking.
- **Database guarantee:** an `ExclusionConstraint` (`btree_gist`) on `(mentor_id WITH =, tstzrange(start_at, blocked_until) WITH &&)` filtered to active statuses, and a matching one on `student_id`. Even if application logic had a bug, Postgres refuses overlapping bookings. The resulting `IntegrityError` maps to `409 slot_unavailable` or `409 student_busy`, using the violated constraint's name. A test races four threads for one slot and asserts exactly one booking.
- **State machine:** transitions are declared in one table (`bookings/models.py::TRANSITIONS`) and applied only through `bookings/services.py::_transition`. Each transition writes a `BookingEvent` row (who, from, to, when, why).
- **Time-based jobs:** `manage.py expire_bookings` expires lapsed payment holds and unanswered requests. It's idempotent and uses `SKIP LOCKED`. A `scheduler` container runs it every minute in dev, and cron or a platform scheduler should run it in prod. Sessions are completed by the mentor; automatic completion is a follow-up. A task queue (Celery/RQ or Django's tasks framework after an upgrade) is deferred until real async load needs it.

### 4.5 Payments

Full design, provider research, accounting rules and test status: **[PAYMENTS.md](PAYMENTS.md)**.

> **Status:** implemented behind a provider abstraction with a Stripe adapter, and tested against mocked provider responses and Stripe's official mock server. **No provider has been chosen** (it depends on the business's country) and nothing has run against a real provider account, so live payments and payouts are **not** operational. With `PAYMENT_PROVIDER` empty, paid bookings are refused.

- `payments/providers/base.py` defines the `PaymentProvider` protocol (`create_checkout`, `expire_checkout`, `capture`, `cancel_authorization`, `refund`, `parse_webhook`). `providers/stripe.py` implements it. There is no fake provider in the application: test doubles live only in the test suite.
- **Flow.** The hold is created at booking, then checkout (hosted page, manual capture, amount from the server) → signed webhook → payment `authorized`, booking `requested` → mentor accepts → capture → `confirmed`. The browser's return from checkout only re-reads the booking.
- **Idempotency.** `WebhookEvent (provider, event_id)` is UNIQUE and claimed under a row lock in the processing transaction. Payment transitions are monotonic. Provider calls carry idempotency keys (`checkout-`, `capture-`, `cancel-`, `refund-<id>`). Refund rows are committed before the provider is called.
- **Verification.** The webhook signature is checked against the raw body before anything else (Stripe: HMAC-SHA256, 5-minute tolerance). Amount, currency and live/test mode must match the payment.
- **Money.** Integer minor units only. Commission is in basis points (default `PLATFORM_FEE_BPS=1500`, optional admin per-mentor override) and snapshotted per payment. Refunds reverse commission and mentor share proportionally. Test-mode payments are never revenue.
- **Payouts.** Manual records only; no automatic payouts (needs a connected-account product).

### 4.6 Notifications
See **[NOTIFICATIONS.md](NOTIFICATIONS.md)**.
- `apps.notifications` sends transactional email. `notify()` writes an `EmailNotification` row with a unique dedupe key inside the business transaction, and sends **after commit**, so rollbacks and re-processed events never send twice.
- Failures are recorded (exception type only) and retried by the scheduler (`send_notifications`, max 3 attempts).
- Covers account, verification, booking lifecycle, session reminders, payment failure/release and refunds.
- Logs carry ids only, never addresses or content; one-time links are scrubbed after sending.
- Dev email goes to **Mailpit**. Prod uses SMTP/API credentials from env. In-app notifications are not built.

### 4.7 Admin tooling
- **Django admin** (at `/django-admin/`, staff-only, separate from `/admin` UI routes) for low-level data inspection and break-glass fixes. Payment, refund, webhook and email records are read-only there.
- **Custom admin pages in Next.js** cover the product workflows: users, verification queue, bookings (cancel with or without refund), payments and refunds (partial/full refunds), reports, review moderation, audit log, email delivery log, and stats with live and test money separated. They go through the same API: every `/admin/` endpoint requires role `admin` (tested for every route and method), and every action writes to the audit log.

### 4.8 Error format
All API errors share one shape:

```json
{ "error": { "code": "slot_unavailable", "message": "That time is no longer available.", "details": { } } }
```

Validation errors put field errors in `details.fields`. A custom DRF `EXCEPTION_HANDLER` implements this shape.

## 5. Frontend design

> Implemented in the FE milestone and integrated with the API in the INT milestone. Developer-facing details are in [frontend/README.md](../frontend/README.md).

- **One data source.** `lib/api/contract.ts` defines the `DataApi` used by every screen, and `lib/api/live.ts` implements it against Django. The interim mock/demo-data layer was removed once the API existed, so there's a single code path.
- **Contract check.** `lib/api/generated.ts` is generated from `docs/openapi.yaml` (`make gen-api`). `lib/api/contract-check.ts` asserts, at compile time, two things:
  - backend responses are assignable to the UI types, so the UI never relies on a field the API doesn't return;
  - UI request bodies are assignable to the backend's request types.
- **Access.** `requireRole()` uses `GET /auth/me/`. The admin area additionally requires `is_admin`, which the backend computes from role and staff status.
- **Payments.** The web app reads `GET /config/`. While `payments_enabled` is false, paid services are labelled and can't be requested (the API refuses them too).
- **Cache Components:** request-time reads (cookies, params, search params, API data) sit inside `<Suspense>`. Static shells prerender, and data streams in. `notFound()` inside a streamed boundary still returns HTTP 200 with a `noindex` tag; this is expected with streaming.
- **Rewrites are resolved at build time.** `INTERNAL_API_URL` must be set when running `next build` as well as at runtime.

- **Rendering:** public pages (landing, search, mentor profile) are Server Components for SEO and fast first paint. Search state lives in URL query params, so it can be shared and works with the back button. Interactive widgets (slot picker, forms) are Client Components.
- **Data access:**
  - `lib/data/server.ts` is for Server Components. Its transport forwards cookies to `INTERNAL_API_URL`.
  - `lib/data/client.ts` is for Client Components. Its transport is same-origin `/api/v1` with an `X-CSRFToken` header.
  - Both share one `createTransport()` (`lib/api/http.ts`) that returns typed results or throws `ApiError`.
  - Dashboard screens load data client-side with `useApiQuery`. A 401 redirects to `/login?next=…&reason=expired`.
  - Types currently live in `lib/api/types.ts` (hand-written from this spec). From M1 they will be generated with `openapi-typescript` from the drf-spectacular schema (`pnpm gen:api`), and CI will fail if they drift.
- **Forms:** React Hook Form + Zod. Server validation errors from `details.fields` map back onto form fields.
- **Design system:**
  - shadcn/ui primitives themed through CSS variables: a neutral slate base, one trustworthy primary (deep teal/indigo), and semantic success/warning/destructive colors.
  - Inter or a system font stack, a 4px spacing scale, and a restrained radius and shadow.
  - Gradients and decorative animation are avoided. Motion is limited to state feedback and respects `prefers-reduced-motion`.
  - Every data view gets loading (skeleton), empty, error and success states.
- **Timezones:** the API returns UTC ISO strings. The UI formats them in the user's profile timezone (falling back to the browser's) with `Intl.DateTimeFormat`, and labels the timezone next to slot pickers.

## 6. Environments and configuration

| Env | How it runs | Settings module |
|---|---|---|
| Local | `make up` (db on host port 5433, mailpit, backend :8000, scheduler) + `make frontend` | `config.settings.dev` |
| Test | `make test`: pytest in the backend container against a separate `test_mentorbridge` database (`--ds=config.settings.test` overrides the container's env); Vitest in Node; `make e2e`: Playwright against a production build (:3200) and the `api-e2e` compose service (:8001, own `mentorbridge_e2e` database, `config.settings.e2e`) | `config.settings.test` |
| Production | Containers behind a TLS reverse proxy, managed PostgreSQL | `config.settings.prod` |

All secrets come from environment variables, and `.env.example` documents every key. `prod.py` refuses to boot if `SECRET_KEY`, `ALLOWED_HOSTS` or `DATABASE_URL` are missing, or if `DEBUG=True`.

## 7. Security architecture

| Concern | Control |
|---|---|
| Password storage | Django hashers (PBKDF2 default; Argon2 when `argon2-cffi` added); password validators |
| Session security | HttpOnly/Secure/SameSite=Lax cookies; session rotation on login; logout invalidates the server session; suspension deletes the user's sessions (reactivation doesn't revive them) |
| CSRF | Django CSRF middleware + DRF `SessionAuthentication`; `CSRF_TRUSTED_ORIGINS` set to the public origin; only the webhook endpoint is exempt (signature-verified instead) |
| Authorization | Role permissions + per-object queryset scoping; 404 for foreign objects |
| Input validation | DRF serializers (server, authoritative) + Zod (client, UX only); DB `CHECK` constraints on ratings, prices, durations, time ranges |
| Rate limiting | DRF scoped throttles on login (per IP and per account, with look-alike emails folded together), register, password reset, booking creation, report creation; the Django admin login is throttled too (per IP and account). DB-backed cache so limits hold across worker processes. Server-rendered pages forward the visitor's IP, so SSR traffic isn't one shared bucket |
| Abuse limits | At most `MAX_PENDING_BOOKINGS_PER_STUDENT` (5) unconfirmed bookings per student and 2 per student–mentor pair, so one account can't block calendars. Search uses subqueries (no join blow-up), and production sets a 30 s PostgreSQL `statement_timeout` |
| Booking integrity | Row locks + Postgres exclusion constraints |
| Payment integrity | Server-computed amounts; webhook signature verification; unique event IDs; monotonic state; provider idempotency keys; frontend success messages ignored |
| Data exposure | Separate public/private serializers. No email addresses or contact details are exposed to other users; the meeting link only to participants of a confirmed booking; payment records only to admins |
| Uploads | Content-based image validation (Pillow; JPEG/PNG/WebP; 2 MB; 4000 px; decompression bombs rejected); random storage names; served by the reverse proxy with `nosniff` and a sandboxing CSP |
| Headers | `SECURE_*` settings, HSTS in prod, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: DENY`; a Content-Security-Policy on production builds (`frame-ancestors 'none'`, same-origin scripts and connections; `'unsafe-inline'` remains for Next.js's inline scripts) |
| Redirects | `?next=` after login accepts same-site paths only, checked after URL normalisation (dot-segments can't produce `//host`); checkout follows https URLs only |
| Logging | Plain-text logs to stdout with a request ID. Code logs identifiers and error codes only, never emails, tokens, request bodies or payment payloads (asserted by tests for notifications). Access logs record the forwarded client IP |
| Audit | `AuditLogEntry` for admin actions, refund failures and disputes; `BookingEvent` for booking transitions. Reviews, payments, refunds and webhooks are read-only in Django admin |
| Secrets | Env vars only; `.env` git-ignored; no secrets in fixtures or tests |
| Dependencies | Pinned requirements and a pnpm lockfile. No CI yet: `pnpm audit` is run manually, and `pip-audit` / CI are open items (roadmap M7) |

## 8. Key architectural decisions (ADR summary)

| # | Decision | Alternatives considered | Rationale |
|---|---|---|---|
| ADR-1 | Monorepo with `backend/` and `frontend/` | Two repos | One PR changes API + UI + types together |
| ADR-2 | Same-origin deployment, Django session auth + CSRF | JWT in localStorage; JWT in cookies (simplejwt) | Least token-handling surface; built-in revocation; standard Django security |
| ADR-3 | Django 5.2 LTS on Python 3.13 | Django 6.1 | Ecosystem compatibility today; LTS support window |
| ADR-4 | Service/selector layer per app | Fat models / fat views | Testable business logic, clear transaction boundaries |
| ADR-5 | Postgres exclusion constraints for booking overlap | App-level checks only | Correct under concurrency, even with bugs |
| ADR-6 | UUID primary keys for domain models | Bigint + public UUID | Non-enumerable IDs in URLs; simple at MVP scale |
| ADR-7 | Authorize-then-capture payments | Charge then refund on decline | Declines cost nothing, fewer refunds |
| ADR-13 | Provider abstraction; provider chosen by the business's country | Commit to Stripe now | Stripe doesn't serve every country (e.g. Bangladesh); the workflow shouldn't depend on one provider ([PAYMENTS.md §1](PAYMENTS.md#1-choosing-a-provider)) |
| ADR-8 | OpenAPI-generated TS types | Hand-written types | API is the single contract; drift caught in CI |
| ADR-9 | No task queue in MVP; idempotent management commands on a scheduler | Celery + Redis | Fewer moving parts; add when needed |
| ADR-10 | Django admin for back-office + custom Next.js admin for core workflows | Only one of the two | Speed now, polished workflows where they matter |
| ADR-11 | Single currency, integer minor units | Multi-currency | Scope; avoids FX/tax complexity |
| ADR-12 | Mentors supply meeting links | Embedded video SDK | Scope; video is a commodity |

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Custom User model must exist before the first migration | Very costly to change later | Create `users.User` in Milestone 1 before any `migrate` |
| Local Python is 3.9 (unsupported by Django 5.2) | Can't run backend natively | Backend runs in Docker; optional `brew install python@3.13` or `uv` for IDE tooling |
| Cookie/CSRF behaviour through the Next.js dev proxy (Origin vs Host) | Login or POSTs failing with 403 | `CSRF_TRUSTED_ORIGINS` + `USE_X_FORWARDED_HOST`; covered by an E2E login test in M1. The rewrite already preserves trailing slashes, request bodies and the `X-CSRFToken` header (verified against a local echo server) |
| Frontend built before the backend | API shape drift | UI depends only on `DataApi`; replace hand-written types with OpenAPI-generated ones in M1 and fix any drift there |
| Timezone/DST bugs in slot generation | Wrong session times | Pure-function slot engine with DST-boundary unit tests |
| Webhook ordering and retries | Inconsistent payment state | Idempotent, monotonic handlers; reconcile by fetching the PaymentIntent from Stripe |
| Card authorizations expire (~7 days) | Capture fails on late acceptance | Mentor response window (48h) far below the expiry |
| Payout automation requires a connected-account product + KYC; Stripe cross-border payouts only cover US/UK/EEA/CA/CH | Delays mentor payouts | MVP records payouts manually; decide with the provider |
| No payment provider available for the business's country | Paid sessions can't launch | Provider abstraction; research in PAYMENTS.md §1; decision pending the country |
| Exclusion constraints can't run on SQLite | Tests pass locally, fail in prod | Tests always run on PostgreSQL |
| Scope creep across three roles | Slow MVP | Strict milestone gates in the roadmap |
