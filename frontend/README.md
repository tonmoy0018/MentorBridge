# MentorBridge — Frontend

Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind CSS 4 · shadcn/ui (Radix) · React Hook Form + Zod · Vitest · Playwright.

> This version of Next.js has breaking changes compared with older releases. Read the guides in `node_modules/next/dist/docs/` before changing routing, caching or data fetching (see `AGENTS.md`).

## Quick start

The web app always talks to the Django API; there's no mock or demo-data mode.

```bash
# from the repository root
make up            # PostgreSQL, Mailpit, Django API on :8000
make superuser     # an admin account (for approving mentors)
make frontend      # this app on http://localhost:3000, proxying /api/* to :8000
```

## Scripts

| Command | What it does |
|---|---|
| `pnpm dev` | Dev server (set `INTERNAL_API_URL` if the API isn't on `localhost:8000`) |
| `pnpm build` / `pnpm start` | Production build / server |
| `pnpm lint` | ESLint (Next.js core-web-vitals + TypeScript rules) |
| `pnpm typecheck` | Route types + `tsc --noEmit`, **including the API contract check** |
| `pnpm test` | Vitest unit and component tests (`tests/`) |
| `pnpm gen:api` | Regenerate `src/lib/api/generated.ts` from `../docs/openapi.yaml`. Run `make gen-api` from the root to refresh the schema first |
| `pnpm test:e2e` | Playwright against the real stack (see below). Requires Docker |

## Environment variables

| Variable | Scope | Purpose |
|---|---|---|
| `INTERNAL_API_URL` | **server only**, build time + runtime | Django base URL (default `http://localhost:8000`). Used by the `/api/*` rewrites and by Server Components. Rewrites are resolved when you run `next build`, so set it for builds too |

There are no public (`NEXT_PUBLIC_*`) variables and no secrets in the browser bundle.

## How it's organised

```
src/
  app/
    (site)/                 public pages: /, /mentors, /mentors/[id]
    (auth)/                 /login, /signup, /signup/{student,mentor}, /forgot-password, /reset-password, /verify-email
    dashboard/              /dashboard (redirects by role); student/, mentor/, admin/ role-gated sections
  components/               ui/ (shadcn), layout/, mentors/, bookings/, forms/, feedback/, common/, dashboard/, auth/
  features/                 dashboard screens: student/, mentor/, admin/, account/
  hooks/                    useApiQuery (loading/error/expired session), useApiErrorHandler
  lib/
    api/                    types.ts (UI types) · generated.ts (from OpenAPI) · contract-check.ts · live.ts (client)
                            · contract.ts · errors.ts · http.ts · browser/server transports
    data/                   client.ts (Client Components) and server.ts (Server Components: getServerApi,
                            getCurrentUser, requireRole)
  proxy.ts                  fast signed-out redirect for /dashboard/* (not the security boundary)
tests/                      Vitest
e2e/                        Playwright (live stack)
```

### Data and contract rules

- UI code uses `api` from `@/lib/data/client`, or `getServerApi()` / `getCurrentUser()` / `requireRole()` from `@/lib/data/server`. Components never call `fetch` directly.
- **Contract check.** Backend response types must be assignable to the UI types, and UI request types to the backend's. This means the UI can't read a field the API doesn't return, or send one it doesn't accept. Any drift fails `pnpm typecheck`.
- **Search and filtering run on the server.** `/mentors` passes its URL parameters straight to `GET /api/v1/mentors/` and renders one page, nine mentors at a time.
- **Errors.** Every failure is a typed `ApiError`.
  - A `401` sends the user to `/login?next=…&reason=expired`.
  - A `409` or `404` on a booking action refreshes the list, so outdated buttons disappear.
  - Booking dialogs disable themselves while a request is in flight (no double submissions).
  - Write requests are never retried automatically.

### Authentication and access

- **Session.** Django's session cookie (HttpOnly) plus a CSRF token, on one origin: Next.js rewrites `/api/*` to Django. Nothing sensitive is stored in browser storage.
- **Roles.** Roles come from `GET /api/v1/auth/me/`.
  - `requireRole()` sends signed-out users to log in, and users with the wrong role to their own dashboard.
  - The admin area also requires `is_admin` (role=admin **and** staff on the backend).
- **API enforcement.** Django enforces every permission again on every request. The UI gates are for navigation, not security.

### Booking states

The UI uses only the backend's states: `pending_payment`, `requested`, `confirmed`, `completed`, `declined`, `cancelled` and `expired`.

- **Actions** come from `bookingPermissions()`, which is based only on status and start time. Closed bookings offer no session actions, and the meeting link only shows for `confirmed`.
- **"Payment failed"** isn't a booking state on the backend. A declined card leaves the booking `pending_payment` (the student can retry with **Pay now**); an unpaid hold expires.
- **Paid services** can't be booked while `GET /api/v1/config/` reports `payments_enabled: false`. The backend refuses them too. When enabled, booking a paid service holds the slot and redirects to the provider's hosted checkout (https only). The return to `/dashboard/student/bookings?checkout=<id>` only **re-reads** the booking; it never marks anything paid. A "Test mode" notice is shown while `payments_livemode` is false.

### Cache Components

`cacheComponents` is enabled. Anything that reads cookies, params, search params or live data renders inside `<Suspense>` and streams at request time. `getServerApi()` calls `connection()` for this reason.

## End-to-end tests

`pnpm test:e2e` (or `make e2e`) starts:
- PostgreSQL and Mailpit;
- the `api-e2e` compose service on `:8001`, using its own `mentorbridge_e2e` database (created if missing and never reset) with relaxed rate limits;
- a production build of this app on `:3200`.

It then runs:
- `journey.spec.ts`: the full marketplace journey. Students and a mentor register, the mentor onboards (profile, services, hours), an admin approves them, and a student searches, opens the profile and books. Two students race for one slot. The mentor accepts, both dashboards show the session, the student cancels, and the released slot is rebooked. Access control is checked throughout.
- `auth.spec.ts` and `public.spec.ts`: on desktop and on a phone viewport.

Every run uses new, uniquely named accounts. The E2E admin account (`e2e-admin@example.com`) exists only in the E2E database.
