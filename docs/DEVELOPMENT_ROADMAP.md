# MentorBridge — Development Roadmap

Last updated: 2026-10-27
Legend: `[x]` done · `[ ]` pending · `[!]` blocked (reason given) · `[~]` in progress

Each milestone ends in a working, tested slice. A milestone is complete only when its acceptance criteria pass **and** its tests have been run and pass in CI or locally (recorded in the milestone log below).

## Milestone overview

| # | Milestone | Outcome | Status |
|---|---|---|---|
| M0 | Foundation & planning | Repo, docs, decisions | ✅ Done |
| FE | Frontend foundation (requested ahead of the backend) | Public pages, auth screens, all three dashboards on a typed API client + labelled mock data layer | ✅ Done |
| INT | Frontend ↔ backend integration | Web app on real API data only; contract check; live browser E2E of the full journey | ✅ Done |
| M1 | Skeleton, auth & roles (backend) | Running stack; register/login as student or mentor | ✅ Done |
| M2 | Mentor profiles, discovery & verification | Profiles, services, admin approval, search | ✅ Backend done; UI wizard pending |
| M3 | Availability & booking | Slot engine; booking lifecycle with conflict prevention | ✅ Backend done; minor follow-ups |
| M4 | Payments & earnings | Stripe checkout, webhooks, capture/refund, payouts | ⚠️ Built + tested against mocks; **not live**: provider blocked on business country + sandbox keys |
| M5 | Reviews, wishlist, goals, notifications | Post-session loop + student tools + notifications | ✅ Done except in-app notifications and a production email provider |
| M6 | Admin operations | Users, bookings, reports, payouts, stats | ✅ Done (refunds, review moderation, audit log viewer, email log) |
| M7 | Hardening & launch readiness | Security/a11y/perf passes, CI/CD, production config, runbooks | Pending |

MVP launch = M1–M7 complete.

---

## M0 — Foundation & planning ✅
- [x] Inspect repository (empty) and local toolchain
- [x] Initialize git repository (`main` branch)
- [x] Product requirements — `docs/PRODUCT_REQUIREMENTS.md`
- [x] Architecture & ADRs — `docs/ARCHITECTURE.md`
- [x] Database schema plan — `docs/DATABASE_SCHEMA.md`
- [x] API specification plan — `docs/API_SPECIFICATION.md`
- [x] Roadmap & checklist — this file
- [x] README with setup commands, `.gitignore`, `.editorconfig`, `.env.example`

---

## FE — Frontend foundation ✅

> Historical note: the mock data layer described below was removed in the INT milestone.

Built before the backend at the product owner's request. The UI talks to a typed API contract (`frontend/src/lib/api/contract.ts`). Until Django exists, it runs on a mock data layer that's clearly labelled in the UI. Details are in [frontend/README.md](../frontend/README.md).

### Done
- [x] Next.js 16.4 + React 19 + TS 5.9 strict + Tailwind 4 + shadcn/ui (Radix) scaffold with pnpm
- [x] Design tokens (teal primary, slate neutrals, semantic success/warning/info), enlarged touch targets, focus styles, reduced-motion support
- [x] Typed models, `ApiError` normalisation, browser transport (same-origin, CSRF header) and server transport (cookie forwarding)
- [x] `DataApi` contract with live Django client and in-memory mock implementation. Auth is always live and never mocked
- [x] Live builds alias `@/mocks/*` to a stub. Verified: 0 demo-data references in the live client and server output
- [x] `next.config.ts`: `/api/*` → Django rewrites (trailing slashes preserved), security headers, guard against mock-mode production builds
- [x] `proxy.ts` signed-out redirect for `/dashboard/*`; role-gated dashboard layouts (`requireRole`). Both are coarse UI gates only
- [x] Public: homepage (hero, search, categories, featured mentors, how it works, student/mentor benefits, FAQ, footer), `/mentors` (URL-driven search, filters, sort, pagination, active-filter chips, mobile filter sheet), `/mentors/[id]` (profile, experience, services, slot picker in viewer's timezone, booking request, reviews, save)
- [x] Auth: `/login`, `/signup` (chooser), `/signup/student`, `/signup/mentor`, `/forgot-password`, `/reset-password`. Zod validation, server field-error mapping, safe `?next=` redirects, no account enumeration
- [x] Student dashboard: overview, bookings (tabs + cancel), saved mentors, goals (CRUD), settings
- [x] Mentor dashboard: overview (requests + verification notice), profile editor + experience + submit for verification, services, weekly availability + booking settings, bookings (accept/decline/complete/cancel), earnings (summary, ledger, payouts), settings
- [x] Admin dashboard: stats, users (search + suspend/reactivate), verification queue (approve/reject with feedback), bookings, payments (read-only), reports (resolve)
- [x] Reusable components: Navbar, Footer, MentorCard, MentorFilters, CategoryCard, SearchBar, RatingDisplay, PriceDisplay, BookingCard, BookingStatusBadge, ProfileHeader, FormField, LoadingState, EmptyState, ErrorState, ConfirmationDialog (+ Pagination, StatCard, StatusBadge, QueryView, VerifiedBadge, MentorAvatar)
- [x] Vitest (57 tests) + Playwright (19 specs × desktop/mobile) + ESLint + `tsc` all passing

### Follow-ups (not blocking)
- [ ] Replace hand-written `lib/api/types.ts` with types generated from the Django OpenAPI schema (`pnpm gen:api`) once M1 exists
- [ ] Review submission UI for completed bookings (M5)
- [ ] Notifications UI (M5); report-content entry points for users (M6)
- [x] Admin booking cancellation and refunds (payments stage)
- [ ] Date-specific availability overrides UI (M3)
- [ ] Mentor avatar upload (M2)
- [ ] Content-Security-Policy with nonces (M7)
- [ ] Automated accessibility checks (axe) in Playwright (M7)
- [ ] Dark theme (tokens exist; no toggle yet)

## BE — Backend (M1 + backend parts of M2, M3, M5, M6) ✅

Built in one pass against the frontend's existing API contract (`frontend/src/lib/api/contract.ts`). The only frontend change: industries now load from `/categories/`. Details: [backend/README.md](../backend/README.md), [API_SPECIFICATION.md](API_SPECIFICATION.md).

### M1 — Skeleton, auth & roles ✅
- [x] `docker-compose.yml` (PostgreSQL 17.11 on host port 5433, Mailpit, backend, scheduler), `backend/Dockerfile` (Python 3.13.18, non-root), `Makefile`, `.env.example`
- [x] `config/settings/{base,dev,test,prod}.py`; prod refuses insecure config
- [x] `apps/common`: UUID/timestamp bases, error envelope, pagination, permissions, throttles, request-ID logging, audit log, health
- [x] `apps/users`: custom `User` (email login, role, timezone) created before the first migration
- [x] Auth: csrf, register, login, logout, me (GET/PATCH), password change, password reset, email verification
- [x] CSRF enforced on anonymous auth endpoints too; 401 vs 403 vs 404 semantics
- [x] Scoped rate limits (per IP and per login email) on a DB-backed cache
- [x] OpenAPI schema and Swagger UI; `docs/openapi.yaml` exported; validates with `--fail-on-warn`
- [x] Django admin at `/django-admin/`; payments, bookings and audit log are read-only there
- [x] Live E2E through the real frontend: register → dashboard → logout → login redirect; student blocked from admin pages and API (403)
- [ ] Replace hand-written frontend types with types generated from the OpenAPI schema (`pnpm gen:api`)
- [ ] Commit the live E2E flow as a Playwright project that starts the backend (currently a manual verification script)

### M2 — Mentor profiles, discovery & verification (backend ✅)
- [x] Taxonomy (Category, Profession, Skill, Language) + seed migration
- [x] MentorProfile, MentorSkill, MentorExperience, MentorService + self-service API; avatar upload with content validation
- [x] StudentProfile API
- [x] Verification: submit (completeness check) → admin approve/reject with reason; audit log + email; mentors can never set their own status
- [x] Public search: q, industry, profession, skill, country, language, price range, availability, ordering, pagination
- [ ] Mentor onboarding wizard in the UI (profile editor exists)
- [ ] Dev seed command for clearly-labelled demo mentors (left in `pending`, so approval still goes through the admin workflow)

### M3 — Availability & booking (backend ✅)
- [x] Weekly rules (atomic replace, overlap validation) + dated exceptions; rules keep a time zone in sync with the profile
- [x] Pure, DST-aware slot engine + public availability endpoint
- [x] Booking model with two PostgreSQL exclusion constraints (mentor incl. buffer; student) + BookingEvent audit trail
- [x] Services: create (mentor row lock, re-validation, server-side price snapshot), accept, decline, cancel (policy + refund outcome), complete; one transition table
- [x] Scheduler: `expire_bookings` (lapsed holds, unanswered requests)
- [ ] Automatic completion of past sessions (mentors mark them complete for now)
- [ ] Frontend UI for availability exceptions

### M4 — Payments & earnings (built and tested against mocks; **not live**; provider undecided)
See [PAYMENTS.md](PAYMENTS.md).
- [x] Provider research and decision record (§1); provider abstraction (`PaymentProvider`) + Stripe adapter
- [x] Checkout with manual capture; server-side amounts; idempotency keys on every provider call; slot hold extended to the checkout lifetime
- [x] Webhook endpoint: signature verification, `WebhookEvent` dedupe, monotonic transitions, amount/currency/mode checks
- [x] Capture on accept (auto-accept too); release on decline, expiry and cancellation; late authorisations released
- [x] Configurable commission (basis points, per-mentor admin override, snapshotted per payment); full breakdown per transaction
- [x] Refunds (policy-driven, admin partial/full), refund webhooks, provider-side refunds, disputes (lost → reversal)
- [x] Accounting: test-mode payments excluded from revenue; provider fees recorded; earnings net of refunds
- [x] Frontend: book-and-pay, "Pay now", checkout return that only re-reads the booking, test-mode notices, commission on Earnings
- [x] Tests: 50 payment tests (mocked provider, real signatures) + `make test-stripe-mock` (request shapes vs Stripe's official mock)
- [!] **Business country of registration → provider choice — blocked: product owner** (Stripe doesn't serve e.g. Bangladesh)
- [!] Provider **sandbox** credentials, then a full sandbox run (§9 checklist) — **blocked on the above**
- [ ] Tax treatment (VAT/GST, withholding) — needs an accountant
- [ ] Automatic payouts (connected accounts) — depends on the provider; payouts are manual records until then
- [ ] Reconciliation job (fetch provider state for payments stuck in `created`/`authorized`)

### M5 — Reviews, wishlist, goals, notifications (backend ✅; in-app notifications open)
- [x] Reviews: completed bookings only, one per booking, rating aggregation, public list
- [x] Saved mentors and career goals APIs
- [x] Review submission UI; email-verification page (`/verify-email`)
- [x] Notifications app: templated booking, payment and refund emails; 24 h reminders; dedupe keys; retries; private-data-free logs ([NOTIFICATIONS.md](NOTIFICATIONS.md))
- [ ] In-app notifications
- [!] Production email provider — **blocked: provider choice pending**

### M6 — Admin operations ✅
- [x] Users: list/search, suspend (sessions stop working) / reactivate; can't target self or other admins
- [x] Verification queue, bookings, reports (resolve, optionally hide review), stats with a date range and live/test money split
- [x] Admin booking cancellation (with or without refund); payment refunds (partial/full); refunds list
- [x] Review moderation (hide/publish with rating recalculation)
- [x] Audit log for admin actions, refund failures and disputes, with a viewer in the admin UI; email delivery log
- [x] Permission test across every `/api/v1/admin/` route and method

## INT — Frontend ↔ backend integration ✅

### Done
- [x] Mock/demo-data layer removed; every screen uses the Django API (`NEXT_PUBLIC_API_MODE` and preview dashboards are gone)
- [x] Generated API types from OpenAPI (`pnpm gen:api`) plus a compile-time contract check against the UI types. It found and fixed several frontend assumptions: payment statuses, payout method, service durations, country codes and report fields
- [x] Backend additions the UI needs:
  - `CurrentUser.is_admin` and `Booking.has_review`;
  - public `GET /config/`;
  - paid bookings refused (503) while payments are disabled, instead of dead-end holds;
  - meeting link required for verification, with a fallback to the mentor's current link;
  - response schemas mark always-present fields as required.
- [x] Auth: real login, registration and logout. Signed-in users skip the auth pages. `/verify-email` page and resend in Settings. The admin area is gated on `is_admin`
- [x] Booking UI:
  - paid services are labelled and unbookable while payments are off;
  - a slot conflict keeps the dialog open with a clear message and refreshes the times;
  - `refund_outcome` and expiry are explained;
  - students can leave reviews after completion;
  - stale actions trigger a refresh.
- [x] Admin: payment and refund statuses match the API; resolving a report can hide the review
- [x] Live Playwright suite (`make e2e`) on a dedicated E2E database:
  - full journey A–L, including the two-student race;
  - auth and public pages on desktop and mobile.
- [x] Bugs found by the live E2E run and fixed:
  - a mail-server outage made registration return 500 after the account was created;
  - a slot conflict closed the booking dialog without showing the error;
  - confirmed sessions could have no meeting link.

### Not done / limitations
- [x] Payments: implemented in the payments stage (see M4); still not live
- [ ] Review submission isn't covered by E2E: completion needs the session start to pass. It's covered by backend and unit tests
- [ ] Mentor avatar upload UI (the API exists); availability exceptions UI (the API exists)
- [ ] Sessions aren't completed automatically; mentors mark them complete
- [x] Booking emails (payments stage); in-app notifications still open
- [ ] E2E isn't wired into CI yet (M7)

## PRR — Production-readiness review (2026-11-06)

Independent backend and frontend reviews plus a local rehearsal of the production stack ([DEPLOYMENT.md](DEPLOYMENT.md)).

### Fixed (with regression tests)
- [x] **Search DoS:** each search term added JOIN pairs, so 4 terms cost ~1e11× one term. It now uses subqueries, and production has a 30 s `statement_timeout`.
- [x] **Server-rendered pages broken in production:** Django's HTTPS redirect hit Next.js's internal HTTP calls. Next.js now forwards `X-Forwarded-Proto/Host/For`.
- [x] **SSR traffic shared one rate-limit bucket:** all anonymous page views counted against the Next.js server's IP. Fixed by the same header forwarding.
- [x] **Stranded captures:** money captured while the booking stayed `requested` or closed. A capture now confirms the booking, or refunds it automatically if the booking closed; a retried accept is idempotent.
- [x] **Django admin login** had no throttling (now 10 failures per IP and 5 per account per 15 min).
- [x] **Profile saves overwrote admin decisions** (verification status, rating, commission). Saves now write only the changed fields.
- [x] **Per-account login limit bypass** with look-alike emails (`ſ`, `ı`).
- [x] **Calendar blocking:** one student could hold unlimited slots. Now capped at 5 pending bookings per student and 2 per mentor.
- [x] **Smaller backend fixes:**
  - decompression-bomb avatar → 500;
  - reactivation revived old sessions;
  - registration race → 500;
  - HTML-escaped email subjects;
  - reviews editable or deletable in Django admin without a rating recalculation;
  - lost dispute plus pending refund broke the refund constraint.
- [x] **Open redirect after login** via dot-segments (`/.//evil.example`).
- [x] **Bookings board** dropped the newest bookings past 50. Admin lists (including the verification queue), saved mentors and earnings were cut at 20. All are paginated now.
- [x] **Frontend fixes:**
  - dashboard and global error boundaries;
  - production Content-Security-Policy, with E2E checks for no console errors;
  - 403 messages no longer blame the role for CSRF failures;
  - the checkout notice no longer promises updates it doesn't deliver, and handles session expiry;
  - Back from the provider no longer leaves a stuck button.
- [x] **Dependencies:** the `shadcn` CLI moved to devDependencies. `pnpm audit --prod` went from 2 advisories (1 moderate, 1 low) to 0.
- [x] **Production configuration** (`deploy/`, frontend Dockerfile):
  - `prod.py` refuses unsafe or misconfigured settings;
  - static and media are served;
  - access logs record the client IP;
  - backup and restore were tested.

### Known, not fixed (accepted for MVP or needing a decision)
- [ ] Mentors can change their **name** after approval without re-review or audit.
- [ ] Registration reveals whether an email is registered (login and reset don't).
- [ ] Suspending a mentor doesn't cancel their upcoming bookings; an admin must cancel them (Admin → Bookings).
- [ ] Mentors can mark a session completed as soon as it starts, which makes earnings "available" early. There's no no-show process for students.
- [ ] `available_within_days` search is CPU-heavy: slot generation for up to 500 mentors, in Python.
- [ ] **Frontend:**
  - a few texts hard-code the 24 h cancellation window;
  - an out-of-range directory page shows an error, not the empty state;
  - signed-in visitors to `/login?next=` lose `next`;
  - tall sticky sidebars on short screens;
  - login/signup buttons re-enable before navigation;
  - the directory makes 6 API calls per view (taxonomy isn't cached).
- [ ] Development-only: IP rate limits can be spoofed through the dev proxy. Production overwrites the header at Caddy.
- [ ] Media on a local volume: single host only. Use object storage before scaling out.

## M7 — Hardening & launch readiness
- [ ] GitHub Actions CI: lint, typecheck, backend tests (Postgres service), frontend tests, Playwright, `pip-audit`, `pnpm audit`, OpenAPI type drift check
- [ ] Security review (OWASP ASVS L1 checklist), CSP, HSTS, cookie flags verified in prod config
- [ ] Accessibility audit (axe in Playwright + manual keyboard/screen reader pass)
- [ ] Performance: query counts on list endpoints, indexes verified with `EXPLAIN`, image optimization
- [ ] Production deployment config (reverse proxy, gunicorn, static/media storage, backups)
- [!] Hosting/target platform — **blocked: decision pending**
- [ ] Error monitoring + structured logs shipping
- [ ] Runbooks: refunds, failed webhooks, restoring backups

---

## Cross-cutting backlog (post-MVP)
- Calendar sync (Google/Outlook), ICS attachments
- Automated mentor payouts (provider connected accounts)
- Mentor review replies, re-verification on material profile changes
- Social login, 2FA for admins
- Full-text/trigram search ranking
- Multi-currency

## Known blockers & decisions needed
| Item | Needed by | Owner |
|---|---|---|
| **Business country of registration** (decides the payment provider) | M4 | Product owner |
| Payment provider sandbox credentials | M4 | Product owner |
| Tax treatment of commission and session fees | M4 / launch | Product owner + accountant |
| Email provider choice | M5 (prod), M7 | Product owner |
| Launch geography/currency | M4 | Product owner |
| Hosting platform + domain + SMTP provider | M7 | Product owner / engineering |
| **Privacy policy and terms of service** (none exist; payment providers require them) | Launch | Product owner + legal |
| Mentor verification evidence policy | M2 | Product owner |
| Local Python 3.13 (optional, for IDE tooling; backend runs in Docker) | — | Developer |

## Milestone log
| Date | Milestone | Notes | Tests run |
|---|---|---|---|
| 2026-10-27 | M0 | Repo was empty. Git initialized; planning docs written. No application code yet. | None — no code to test |
| 2026-10-27 | FE | Frontend built on a mock data layer, ahead of the backend at the product owner's request. Routes follow the requested structure (`/signup`, `/dashboard/{role}/…`, `/mentors/[id]`); the docs were updated to match. | `pnpm lint` ✅ · `pnpm typecheck` ✅ · `pnpm test` 57/57 ✅ · `pnpm test:e2e` 37 passed, 1 skipped (mobile-only test in desktop project) ✅ · live `pnpm build` ✅ · mock `pnpm build` ✅ · manual checks: API rewrite against a local echo server, signed-out dashboard redirect, error states with failing API, security headers, demo banner absent in live mode |
| 2026-10-27 | BE | Django/DRF/PostgreSQL backend matching the frontend contract. Integration run found and fixed a 500 on `GET /categories/` (counts not requested) and added a regression test. A throwaway `mentorbridge_integration` database was created for the live run and dropped afterwards; the dev database holds no test data. | `pytest` 143/143 ✅ (PostgreSQL) · `ruff check` ✅ · `ruff format --check` ✅ · `makemigrations --check` ✅ · `spectacular --validate --fail-on-warn` ✅ · frontend `typecheck` ✅ + `vitest` 57/57 ✅ · live browser flow (signup → profile → service → hours → verification → admin approve → student booking → mentor accept → confirmed + meeting link → logout) ✅ |
| 2026-10-27 | INT | Web app integrated with the API; mock layer removed; contract check added. Live E2E found 3 real bugs, all fixed with regression tests. | backend `pytest` 150/150 ✅ · `ruff` ✅ · `makemigrations --check` ✅ · OpenAPI `--fail-on-warn` ✅ · frontend `lint` ✅ · `typecheck` + contract check ✅ · `vitest` 66/66 ✅ · `playwright` 35/35 ✅ against the real stack, twice in a row |
| 2026-11-06 | M4/M5/M6 | Payments (provider abstraction + Stripe adapter, webhooks, commission, refunds, disputes), transactional email and admin operations. **Live payments and payouts are not operational: no provider chosen, no real provider account used.** Found and fixed: late authorisations on an already-cancelled checkout stayed held; reset/verification links persisted in the email table; email links were HTML-escaped; `AdminStats` schema dropped the `test` block; `Refund.status` documented with the wrong enum; compose didn't pass payment settings. | backend `pytest` 307 passed, 2 skipped (stripe-mock tests, run separately: 2/2 ✅ against `stripe/stripe-mock:v0.206.0`) ✅ · `ruff` ✅ · `makemigrations --check` ✅ · OpenAPI `--fail-on-warn` ✅ · mutation check: bypassing signature verification or the late-payment fix fails tests ✅ · frontend `lint` ✅ · `typecheck` + contract check ✅ · `vitest` 79/79 ✅ · `playwright` 35/35 ✅ (payments disabled) |
| 2026-11-06 | PRR | Production-readiness review: independent backend and frontend audits, fixes for all high and medium findings (see PRR), production configuration in `deploy/` rehearsed locally over HTTPS (images, prod settings, migrations, smoke tests, avatar upload, backup and restore). **Not deployed publicly.** | backend `pytest` 327 passed, 2 skipped (stripe-mock 2/2 ✅ separately) ✅ · `ruff` ✅ · `makemigrations --check` ✅ · OpenAPI `--fail-on-warn` ✅ · `check --deploy` (prod settings, in the prod image): only the opt-in HSTS preload warning · mutation check: the old search query fails the new cost test ✅ · frontend `lint` ✅ · `typecheck` + contract ✅ · `vitest` 85/85 ✅ · `playwright` 37/37 ✅ (incl. no console errors under CSP) · `pnpm audit --prod`: 0 known vulnerabilities · production Docker images build ✅ |
