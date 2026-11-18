# MentorBridge — Product Requirements

Status: Draft v0.1 (Milestone 0)
Last updated: 2026-10-27

## 1. Summary

MentorBridge is a two-sided mentorship marketplace. **Students** (students and early-career professionals) discover and book paid 1:1 sessions with **Mentors** (experienced professionals). **Administrators** keep the marketplace trustworthy by verifying mentors, moderating content and overseeing bookings and payments.

The MVP aims to prove one loop end to end:

> A student finds a verified mentor → books an available slot → pays → the mentor accepts → the session happens → the student leaves a review → the mentor sees the earning.

## 2. Goals and non-goals

### Goals (MVP)
- Trustworthy discovery: only admin-approved mentors are publicly listed.
- Reliable booking: no double-booked mentors, timezone-correct slots.
- Safe payments: payment state comes only from the payment provider, never from the browser.
- Clear dashboards for each role.
- Responsive, accessible UI (WCAG 2.2 AA target).

### Non-goals (MVP)
- Built-in video calling (mentors provide a meeting link; e.g. Zoom/Google Meet).
- Real-time chat between students and mentors.
- Group sessions, subscriptions or packages.
- Multiple currencies (MVP uses a single platform currency, USD by default).
- Automated mentor payouts (MVP records earnings and payout records; payout automation follows later).
- Native mobile apps.
- Calendar sync (Google/Outlook) — candidate for post-MVP.

## 3. Personas

| Persona | Description | Primary need |
|---|---|---|
| Student | University student or professional with 0–5 years' experience | Find the right person, book quickly, trust the quality |
| Mentor | Professional with meaningful industry experience | Present expertise, control schedule and price, get paid |
| Administrator | MentorBridge staff | Keep supply verified, resolve problems, see marketplace health |

## 4. Roles and permissions

Each account has exactly one role in the MVP: `student`, `mentor` or `admin`. Admin accounts can't be self-registered; they're created by existing admins or via the `createsuperuser` command.

| Capability | Anonymous | Student | Mentor | Admin |
|---|:-:|:-:|:-:|:-:|
| Browse/search approved mentors | ✓ | ✓ | ✓ | ✓ |
| View public mentor profile, services, reviews | ✓ | ✓ | ✓ | ✓ |
| Book and pay for a session | – | ✓ | – | – |
| Save mentors / manage goals | – | ✓ | – | – |
| Review a completed session | – | own bookings | – | moderate |
| Manage own mentor profile, services, availability | – | – | ✓ | – |
| Accept/decline/complete bookings | – | – | own bookings | ✓ (override) |
| View earnings and payouts | – | – | own | all |
| Verify mentors, moderate content, manage users | – | – | – | ✓ |
| Report content | – | ✓ | ✓ | – |

## 5. Functional requirements

Priority: **P0** = required for MVP launch, **P1** = MVP if time allows, **P2** = post-MVP.

### 5.1 Accounts and authentication
- **AUTH-1 (P0)** Register with email and password, choosing Student or Mentor.
- **AUTH-2 (P0)** Log in / log out. Sessions use secure HttpOnly cookies.
- **AUTH-3 (P0)** Password reset by email (single-use, time-limited token).
- **AUTH-4 (P0)** Passwords validated using Django's password validators; stored only as salted hashes.
- **AUTH-5 (P1)** Email verification before booking (students) or submitting for verification (mentors).
- **AUTH-6 (P0)** Each user sets a timezone; all times are displayed in the viewer's timezone.
- **AUTH-7 (P2)** Social login (Google, LinkedIn).

### 5.2 Student features
- **STU-1 (P0)** Student profile: name, headline, short bio, country, languages, areas of interest.
- **STU-2 (P0)** Discover mentors with filters: industry, profession, skill, country, language, price range; free-text search; sort by relevance, rating, price.
- **STU-3 (P0)** Mentor detail page: bio, experience timeline, skills, languages, services, ratings and reviews, verification status.
- **STU-4 (P0)** View bookable slots for a selected service, in the student's timezone.
- **STU-5 (P0)** Book a slot with an optional note to the mentor, then pay through the hosted checkout.
- **STU-6 (P0)** Bookings dashboard: upcoming, pending, past and cancelled bookings; cancel within policy.
- **STU-7 (P0)** Wishlist: save and unsave mentors; list saved mentors.
- **STU-8 (P0)** Review a mentor (1–5 stars + comment) once per **completed** booking.
- **STU-9 (P1)** Career goals: create, edit and complete simple goals (title, description, target date, status).
- **STU-10 (P2)** Link goals to bookings; mentor-visible goals.

### 5.3 Mentor features
- **MEN-1 (P0)** Mentor profile: headline, bio, current title/company, profession, industries, skills, languages, country, years of experience, LinkedIn URL, photo.
- **MEN-2 (P0)** Experience entries (work and education) with dates.
- **MEN-3 (P0)** Submit profile for verification; see status (draft, pending, approved, rejected with reason).
- **MEN-4 (P0)** Services: title, description, duration (15–180 min), price; activate/deactivate.
- **MEN-5 (P0)** Weekly recurring availability in the mentor's timezone, plus date-specific overrides (days off / extra hours). Settings: minimum notice, booking horizon, buffer between sessions.
- **MEN-6 (P0)** Booking requests: accept or decline paid requests within a response window (default 48h); auto-accept option.
- **MEN-7 (P0)** Session management: upcoming sessions, history, cancel (with reason), mark completed, meeting link.
- **MEN-8 (P0)** Earnings: per-booking earnings (gross, platform fee, net), totals, payout records.
- **MEN-9 (P1)** Pause accepting new bookings.
- **MEN-10 (P2)** Reply publicly to reviews.

### 5.4 Administrator features
- **ADM-1 (P0)** User management: search, view, suspend/reactivate students and mentors.
- **ADM-2 (P0)** Verification queue: review mentor submissions, approve or reject with reason. Every decision is audit-logged.
- **ADM-3 (P0)** Bookings: search/filter, view history, cancel with refund.
- **ADM-4 (P0)** Reports: users report reviews, profiles or users; admins resolve (dismiss/hide content/suspend user).
- **ADM-5 (P0)** Payments and refunds: list and inspect records; issue full or partial refunds through the provider.
- **ADM-6 (P0)** Payout records: create and mark payouts as paid (manual in MVP).
- **ADM-7 (P1)** Statistics: users by role, approved mentors, bookings by status, gross booking value, refunds, platform revenue over a date range.

### 5.5 Notifications
- **NOT-1 (P0)** Transactional emails: account (password reset), booking requested/accepted/declined/cancelled, payment receipt, verification decision.
- **NOT-2 (P1)** In-app notification list with unread count.
- **NOT-3 (P1)** Session reminder email (24h before).

## 6. Booking and payment rules

### 6.1 Booking lifecycle

```
                  ┌──────────── hold expires (30 min) ───────────► expired
                  │
 create ─► pending_payment ─ payment authorized ─► requested ─ mentor accepts ─► confirmed ─ session ends ─► completed
   (free service skips payment) ──────────────────►    │                            │
                                                       ├─ mentor declines ─► declined│
                                                       ├─ no response (48h) ─► expired
                                                       └─ student cancels ─► cancelled ◄─ either party cancels
```

- A slot is **held** for 30 minutes while the student pays (Stripe Checkout's minimum session lifetime; checkout extends it to at least 31). Held, requested and confirmed bookings all block the slot.
- If the mentor has auto-accept on, `requested` moves straight to `confirmed`.
- A booking can't overlap another active booking for the same mentor (including the mentor's buffer) or for the same student. The database enforces this.
- `completed` happens automatically after the session end time unless the booking is disputed or reported (P1: no-show reporting).

### 6.2 Payments
- Payment is collected through a hosted checkout from the payment provider (Stripe, test mode during development).
- The card is **authorized** at checkout and **captured** when the mentor accepts. A decline or expiry releases the authorization, so no refund is needed.
- The booking only advances when the server receives a **signature-verified webhook**. The browser's success redirect only shows a "confirming payment…" state.
- Webhooks are processed idempotently; replays and duplicates have no effect.
- Platform fee: a configurable percentage (default 15%). Mentor earning = captured amount − platform fee.

### 6.3 Cancellation and refund policy (MVP default, configurable)
| Who cancels | When | Outcome |
|---|---|---|
| Student | Before mentor accepts | Authorization released, no charge |
| Student | ≥ 24h before start | Full refund |
| Student | < 24h before start | No refund (admin may override) |
| Mentor | Any time | Full refund |
| Admin | Any time | Full or partial refund at admin's discretion |

### 6.4 Session formats (online and in person)
- Each service is offered **online**, **in person**, or both. An in-person session costs the service price plus an optional **in-person extra** set by the mentor (e.g. for travel). A free service with an in-person extra is therefore a paid session in person.
- An in-person service shows a public, general **area** (e.g. "Gulshan, Dhaka"), never an exact address.
- The student picks the format when booking. The mentor shares the exact **meeting place** when accepting, or later from the booking. The student sees it only once the session is confirmed. The place is never included in emails or notification logs; emails carry the format and area only.
- Students can filter search results to mentors who meet in person.
- **Administrators** can see the exact place of any in-person booking or seminar, in any status (including after it has taken place), for safety and incident handling. It is never shown in admin lists: the admin asks for it per session, must give a reason, and each request is recorded in the audit log (who, when, why; not the place itself).

### 6.5 One session or several (multi-session options)
- **No free sessions:** every service and seminar seat has a price of at least `MIN_SESSION_PRICE_CENTS` (default $1). Existing free services keep working until edited; editing one requires a price.
- Each service can offer **multi-session options** alongside the single session: N sessions (2–24) with a discount (0–50%), to be used within 7–365 days. There is at most one option per size for a service.
- The price follows the session price in the format the student chooses: N × (price, plus the in-person extra if in person), minus the discount. The student chooses **1 session** or **N sessions** in the booking panel.
- Buying an option goes through checkout. The purchase is usable only once the payment provider confirms payment; the charge is taken immediately (there is no mentor answer to wait for).
- A purchase records its terms (sessions, length, format, price) at purchase time; later edits by the mentor only affect new purchases. Sessions must take place before it expires.
- Each session is booked from the purchase like any booking, at no extra charge. Credits follow §6.3: declined, expired and early-cancelled sessions go back to the purchase; a student cancelling a confirmed session less than 24 hours before it starts uses it up; mentor cancellations always return it.
- A student holds at most one unfinished copy of the same option at a time. A fully refunded purchase can't be used for new bookings.

### Online sessions
- Sessions run on whatever video tool the mentor and student prefer. The mentor's default meeting link (profile) is used unless the mentor sets a link for that session when accepting, or changes it later. The link is shown to the student only once the session is confirmed. MentorBridge does not host video calls.

### 6.6 Group seminars
- A mentor can schedule a **group seminar**: one of their services at a fixed date and time for up to N students (2–100), at a price per seat, online or in person.
- When booking a service that has upcoming seminars, the student chooses **One-to-one** (any open time, mentor accepts) or **Group seminar** (pick a date, take a seat). The choice only appears when such seminars exist.
- Registering takes a seat straight away: free seats are confirmed at once; paid seats are held while the student pays and confirmed when the provider confirms payment (no mentor answer needed). Seats can't be double-taken, and a student can hold only one seat per seminar.
- The seminar blocks the mentor's calendar (plus their buffer), so no one-to-one session can be booked over it, and it can't be scheduled over an existing booking. A student can't hold a seminar seat and another session at the same time.
- Students see seats left, never who else is coming. The mentor sees the attendee list. An in-person seminar shows its area publicly; the exact place is shown only to students with a confirmed seat and is never emailed.
- A student cancelling a seat follows §6.3. A mentor or admin cancelling the seminar cancels every seat with a full refund, and each student gets one email. Mentors can't cancel individual seats.
- Once anyone has registered, the time, length, price, session and format are fixed; the mentor cancels and reschedules instead. Title, description, place, link and seats (not below the number taken) can still change.
- After it starts, the mentor marks the seminar completed; confirmed seats become completed and students can review it.
- Packages (§6.5) apply to one-to-one sessions only.

## 7. Trust and integrity requirements
- Only `approved` mentors appear in search or can be booked.
- The "Verified" badge is shown **only** for mentors approved through the admin verification workflow.
- Reviews only come from students with a completed booking (one review per booking).
- Ratings shown are computed from real reviews. If there are no reviews, the profile shows "No reviews yet".
- Development seed data is clearly marked as demo data (e.g. `@example.com` emails, "Demo" labels), and it's never loaded in production.

## 8. Non-functional requirements
- **Security:** see [ARCHITECTURE.md §7](ARCHITECTURE.md#7-security-architecture).
- **Performance:** mentor search p95 < 500 ms at 10k mentors; page LCP < 2.5 s on a mid-range mobile device.
- **Accessibility:** WCAG 2.2 AA; keyboard navigable; visible focus; labelled form fields; 4.5:1 text contrast.
- **Responsiveness:** layouts tested at 375px, 768px and 1280px+.
- **Reliability:** all state transitions for bookings and payments are transactional and audit-logged.
- **Privacy:** collect minimal personal data. A student's contact details are visible to a mentor only for confirmed bookings. Account deletion is supported (P1).
- **Observability:** structured logs with request IDs, no secrets or personal data in logs.

## 9. Success metrics (post-launch)
- Search → mentor-profile view rate
- Profile view → booking conversion
- Mentor acceptance rate and median response time
- Booking completion rate; cancellation and refund rates
- Review submission rate and average rating

## 10. Open questions
1. Which payment provider and account will be used in production? (Stripe is assumed; Stripe Connect is needed for automated payouts.)
2. Launch geography and currency? (This affects tax, payouts and provider choice.)
3. Should mentors set their own cancellation policy, or should one platform policy apply?
4. Is a minimum price required, or are free sessions allowed? (Currently allowed: price ≥ 0, and free sessions skip checkout.)
5. Which email provider will be used (Postmark, SES, Resend)?
6. What evidence will mentor verification require (LinkedIn only, ID, employer email)?
