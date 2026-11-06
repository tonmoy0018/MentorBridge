# Deployment

How to run MentorBridge locally and in production, and how to deploy, check and roll back a release.

> **Status (2026-11-06):** the production configuration in `deploy/` was rehearsed end to end on a local machine: production images, production settings, HTTPS through Caddy (with its local CA on `localhost`), migrations, smoke tests, and backup and restore. It has **not** been deployed to a public server. Payments stay **off** until a provider is chosen and sandbox-tested ([PAYMENTS.md](PAYMENTS.md)).

## 1. Architecture

```
Internet ──443──► Caddy (TLS, HTTP→HTTPS, only exposed service)
                   ├─ /api/*, /django-admin/*  ──► backend  (Django + gunicorn :8000)
                   ├─ /static/*                ──► collected Django admin assets (volume)
                   ├─ /media/*                 ──► uploaded avatars (volume, served inert)
                   └─ everything else          ──► frontend (Next.js :3000)
                                                    └─ server-side API calls ──► backend:8000
backend, scheduler ──► db (PostgreSQL 17, volume)
```

- **Same origin.** The browser only talks to `https://<SITE_DOMAIN>`, so the session cookie is first-party and CORS is unnecessary.
- **Caddy is the only entry point.** It overwrites client-supplied `X-Forwarded-*` headers. Django (`NUM_PROXIES=1`, `SECURE_PROXY_SSL_HEADER`, `USE_X_FORWARDED_HOST`) and Next.js's server-side calls rely on those headers for client IPs (rate limits) and for HTTPS detection. **Never expose `backend:8000` or `frontend:3000` directly.**
- **Scheduler.** It runs `expire_bookings`, `send_session_reminders` and `send_notifications` every minute.

## 2. Local development

Requires Docker 24+ and Node.js 20.9+ with pnpm (see the root [README](../README.md)).

```bash
cp .env.example .env          # optional: override dev defaults
make up                       # PostgreSQL :5433, Mailpit :8025, API :8000, scheduler
make superuser                # create an admin
make frontend                 # Next.js on http://localhost:3000
```

Development uses `config.settings.dev`:
- `DEBUG` is on and the browsable API is enabled.
- Emails go to Mailpit.
- Payments are off unless you set **test** keys in `.env` (PAYMENTS.md §6).

Checks: `make lint test`, `make frontend-test`, `make e2e`, `make test-stripe-mock`.

## 3. Production configuration

Everything production-specific lives in `deploy/`:

| File | Purpose |
|---|---|
| `deploy/docker-compose.prod.yml` | db, backend (gunicorn), scheduler, frontend, caddy; named volumes `pgdata`, `media`, `static`, `caddy_data` |
| `deploy/Caddyfile` | TLS, routing, HSTS, inert media |
| `deploy/production.env.example` | Every variable; copy to `deploy/.env` on the server (git-ignored) |
| `backend/Dockerfile` | Built with `REQUIREMENTS=requirements.txt` (no dev tools) |
| `frontend/Dockerfile` | `next build` (with `INTERNAL_API_URL=http://backend:8000`) → `next start` |

`config.settings.prod` **refuses to start** when any of these is wrong:
- `DEBUG` is on;
- the secret key is weak or missing;
- `ALLOWED_HOSTS` is empty or contains `*`;
- CSRF or CORS origins aren't `https://`;
- `FRONTEND_URL` isn't `https://`;
- SMTP isn't configured, or another email backend is set;
- `STRIPE_API_BASE` is set.

When it does start, production settings:
- force secure cookies, an HTTPS redirect and HSTS;
- serve the OpenAPI schema and docs to staff only;
- set a 30-second PostgreSQL `statement_timeout`.

### Environment variables

| Variable | Required | Notes |
|---|---|---|
| `SITE_DOMAIN` | yes | Public host name; DNS A/AAAA must point at the server. Derives `ALLOWED_HOSTS` (plus the internal `backend`), `CSRF_TRUSTED_ORIGINS` and `FRONTEND_URL` |
| `ACME_EMAIL` | yes | Contact for Let's Encrypt |
| `DJANGO_SECRET_KEY` | yes | ≥ 50 random characters: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `POSTGRES_PASSWORD` | yes | Long random value (`POSTGRES_DB`, `POSTGRES_USER` optional) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | yes | SMTP from your email provider; set up SPF/DKIM for the sender domain |
| `DJANGO_ADMIN_URL` | no | A less guessable admin path (ends with `/`) |
| `REQUIRE_VERIFIED_EMAIL` | no | Default `true` in production |
| `PLATFORM_CURRENCY`, `PLATFORM_FEE_BPS`, `BOOKING_HOLD_MINUTES`, `MENTOR_RESPONSE_HOURS`, `FREE_CANCELLATION_HOURS` | no | Marketplace rules |
| `MAX_PENDING_BOOKINGS_PER_STUDENT` / `_PER_MENTOR_PAIR` | no | Defaults 5 / 2 |
| `PAYMENT_PROVIDER`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | no | Leave empty until payments are approved (PAYMENTS.md §9). Live keys make payments real |
| `DB_STATEMENT_TIMEOUT_MS` | no | Default 30000; `0` for a long one-off command |
| `GUNICORN_WORKERS`, `LOG_LEVEL` | no | Defaults 3 / INFO |

**Secrets** live only in `deploy/.env` on the server (or your platform's secret store), never in git. `.env` and `.env.*` are git-ignored.

### What each concern needs

| Concern | How it's handled |
|---|---|
| **Frontend hosting** | `frontend` container behind Caddy. On a platform such as Vercel, keep the same origin: route `/api/*` to the backend at the edge and set `INTERNAL_API_URL` at build time |
| **Backend hosting** | `backend` container (gunicorn, 3 workers, 30 s timeout) plus `scheduler`. Any VM or container host with Docker works |
| **PostgreSQL** | `db` service with the `pgdata` volume, or a managed PostgreSQL 17: set `DATABASE_URL` instead and remove `db`. The `btree_gist` extension is created by the migrations (the user needs permission, or create it beforehand) |
| **HTTPS** | Caddy obtains and renews certificates automatically; ports 80 and 443 must be reachable. HSTS is one year. Preload is opt-in (`DJANGO_SECURE_HSTS_PRELOAD`) |
| **CORS / trusted origins** | Same origin, so no CORS. `CSRF_TRUSTED_ORIGINS = https://<SITE_DOMAIN>` |
| **Email** | SMTP variables above. Failures are retried by the scheduler (NOTIFICATIONS.md) |
| **Media** | `media` volume, written by the backend and served by Caddy with `nosniff` and a sandboxing CSP. **Back it up.** For multiple backend hosts, switch to object storage (django-storages); not done yet |
| **Payment credentials** | Environment only. Register the webhook `https://<SITE_DOMAIN>/api/v1/payments/webhooks/stripe/` (PAYMENTS.md §5) |
| **Migrations** | Run explicitly before starting a new version (below); never automatically on start |
| **Backups** | Below |
| **Logging** | Everything goes to stdout and stderr: `docker compose logs`, or ship to your log platform. Access logs show the client IP, request, status, size and time. Application logs carry a request ID and never contain email addresses, tokens or payment payloads |
| **Health checks** | `GET /api/v1/health/` returns `{"status":"ok","db":"ok"}`, or 503 if the database is down. Used by the compose healthcheck; point your uptime monitor at it |

## 4. First deployment

On a server with Docker, DNS pointing at it, and ports 80/443 open:

```bash
git clone https://github.com/tonmoy0018/MentorBridge.git && cd MentorBridge/deploy
cp production.env.example .env && chmod 600 .env     # fill in every required value
alias dc='docker compose -f docker-compose.prod.yml'

dc build
dc up -d db
dc run --rm backend python manage.py migrate --noinput
dc run --rm backend python manage.py createsuperuser   # an admin: role=admin, staff
dc up -d
dc ps                                                  # backend should be "healthy"
```

Then run the smoke tests (§6).

## 5. Deploying a new version

```bash
cd MentorBridge && git fetch && git checkout <release-tag>
cd deploy
dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > pre-release.dump   # backup first (§7)
dc build
dc run --rm backend python manage.py migrate --noinput
dc up -d                       # recreates changed containers
dc ps && dc logs --tail=50 backend frontend
```

Migrations run **before** the new code serves traffic. Keep them backwards-compatible: add columns before using them, remove only in a later release. That way the previous version keeps working against the migrated database if you need to roll back.

## 6. Post-deployment smoke tests

| Check | Expected |
|---|---|
| `curl -I http://<domain>/` | 308 redirect to `https://` |
| `curl https://<domain>/api/v1/health/` | `{"status":"ok","db":"ok"}` |
| `curl https://<domain>/api/v1/config/` | `payments_enabled` as intended (`false` until payments are approved) |
| `curl -I https://<domain>/` | 200 with `strict-transport-security`, `content-security-policy`, `x-frame-options: DENY` |
| `curl https://<domain>/api/v1/schema/` | 401 (staff only) |
| `curl https://<domain>/api/v1/nope/` | Plain 404, no debug page |
| Browser: home, `/mentors`, a mentor profile | Load with data, no console errors |
| Browser: sign up → verification email arrives → sign in → dashboard | Works; cookies are `Secure` and the session cookie is `HttpOnly` |
| `/django-admin/` | Login page with styles |
| As a mentor: upload an avatar | Image appears; its URL is `https://<domain>/media/...` |
| `dc logs scheduler` | Commands running every minute, no errors |
| `dc logs backend` | No 5xx and no 301s on `node` (server-side) requests |

## 7. Backups and restore

**Database**, daily at minimum (cron), kept off the server:

```bash
dc exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > mentorbridge-$(date +%F).dump
```

**Media:**

```bash
dc run --rm --entrypoint sh backend -c 'tar -C /app -cz media' > media-$(date +%F).tgz
```

**Restore** (into a new database first to verify, then switch):

```bash
dc exec -T db sh -c 'createdb -U "$POSTGRES_USER" restore_check'
dc exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d restore_check --no-owner' < mentorbridge-YYYY-MM-DD.dump
```

Both commands were tested in the rehearsal. Test a restore regularly; a backup that has never been restored isn't a backup. Managed PostgreSQL providers offer point-in-time recovery, which is preferable.

## 8. Rollback

1. **Code only (no migration in the release):** check out the previous tag, `dc build && dc up -d`.
2. **With migrations:** if they were additive (§5), roll the code back as in step 1 and leave the schema. To reverse a migration, run `dc run --rm backend python manage.py migrate <app> <previous_migration>`, but only if it has a tested reverse and no data was written that the old schema can't hold.
3. **Data damage:** stop writes (`dc stop backend scheduler frontend`), then restore the last backup (§7). Anything written after it is lost.
4. **Payments:** never roll back past a release that processed payments without reconciling against the provider dashboard. Payment state at the provider is the source of truth.

Tag every release (`git tag vX.Y.Z`) so there is always a known-good version to return to.

## 9. Before going public

- [ ] Real domain, DNS, and an SMTP provider with SPF/DKIM.
- [ ] `deploy/.env` filled with strong, unique secrets.
- [ ] Backups scheduled and copied off the server; a restore tested.
- [ ] Uptime monitoring on `/api/v1/health/`; logs retained.
- [ ] The remaining launch blockers in [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) resolved or accepted (payment provider, legal pages, tax).
