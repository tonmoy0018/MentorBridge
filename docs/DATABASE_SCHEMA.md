# MentorBridge — Database Schema

Status: **implemented** (backend milestone, 2026-10-27). Django migrations in `backend/apps/*/migrations/` are the source of truth, and this document summarises them.

- **Database:** PostgreSQL 17.
- **Extension:** `btree_gist`, created by the first bookings migration and used by the booking exclusion constraints.
- **Seed data:** `taxonomy.0002_seed_reference_data` seeds neutral reference data (categories, professions, skills, languages).

## Conventions
- Table names follow Django's default (`<app>_<model>`).
- Primary keys are `uuid` for everything addressable through the API. Lookup tables use integer keys, and append-only logs use `bigint`.
- Mutable tables have `created_at` and `updated_at` (`timestamptz`).
- **Time:**
  - All instants are `timestamptz`, stored and served in UTC.
  - Weekly availability stores local `time` values together with an IANA time zone.
- **Money:** integer minor units (`*_cents`) plus `currency char(3)`, in one platform currency.
- **Enums:** `varchar` with Django `TextChoices` and a `CHECK` constraint where a bad value would be harmful.
- **Deletion:** financial and booking history is protected with `on_delete=PROTECT`. Profiles are deactivated rather than deleted.

## Overview

```
users_user ─1:1─ students_studentprofile ─M:N─ taxonomy_category (interests)
     │ ├─1:N─ students_careergoal
     │ └─1:N─ students_savedmentor ─N:1─ mentors_mentorprofile
     │
     └─1:1─ mentors_mentorprofile ─M:N─ taxonomy_category ("industries")
                 ├─M:N (through mentors_mentorskill)─ taxonomy_skill
                 ├─M:N─ taxonomy_language ;  N:1─ taxonomy_profession
                 ├─1:N─ mentors_mentorexperience
                 ├─1:N─ mentors_mentorservice
                 ├─1:N─ mentors_availabilityrule / mentors_availabilityexception
                 ├─1:N─ mentors_verificationrequest
                 ├─1:N─ payments_payout
                 └─1:N─ bookings_booking ─N:1─ users_user (student), mentors_mentorservice
                              ├─1:N─ bookings_bookingevent
                              ├─1:N─ payments_payment
                              └─1:1─ reviews_review
moderation_report (typed target) · common_auditlogentry · django_session · django_cache
```

---

## users

### `users_user` (custom `AbstractBaseUser` + `PermissionsMixin`)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| email | varchar(254) | `UNIQUE` and `UNIQUE (lower(email))`; stored lower-cased; login field |
| password | varchar(128) | Django password hash, never plaintext |
| first_name, last_name | varchar(80) | |
| role | varchar(16) | `student` \| `mentor` \| `admin` (CHECK) |
| timezone | varchar(64) | IANA name, validated against `zoneinfo` |
| is_active | bool | false = suspended (no login, sessions rejected) |
| is_staff, is_superuser | bool | admin role ⇒ staff |
| email_verified_at | timestamptz null | |
| last_login, created_at, updated_at | timestamptz | |

Index on `(role, is_active)`.

## taxonomy (seeded reference data)
| Table | Columns |
|---|---|
| `taxonomy_category` | id, name UNIQUE, slug UNIQUE, description, is_active, sort_order, timestamps (the "industries" filter) |
| `taxonomy_profession` | id, name UNIQUE, slug UNIQUE, category_id → category (SET NULL) |
| `taxonomy_skill` | id, name UNIQUE, slug UNIQUE |
| `taxonomy_language` | id, code UNIQUE (ISO 639-1), name |

Countries aren't a table. They're ISO 3166-1 codes stored with `django-countries`.

## students
| Table | Key columns | Constraints |
|---|---|---|
| `students_studentprofile` | id, user_id (1:1), headline, education, bio, country, M2M `interests` → category | |
| `students_savedmentor` | id, student_id → user, mentor_id → mentorprofile, created_at | UNIQUE (student, mentor) |
| `students_careergoal` | id, student_id, title, description, status, target_date, achieved_at | CHECK status ∈ {not_started, in_progress, achieved, archived}; index (student, status) |

## mentors

### `mentors_mentorprofile`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | 1:1 user |
| slug | varchar(80) UNIQUE | public URL |
| headline, bio, current_title (professional title), current_company | text | |
| profession_id | int null | → profession |
| years_experience | smallint | CHECK ≤ 60 |
| country, city (location), timezone | | |
| linkedin_url, meeting_url | varchar | https only, validated by the API |
| avatar | varchar | storage path; random file name |
| verification_status | varchar(16) | `draft` \| `pending` \| `approved` \| `rejected` \| `suspended` (CHECK). **Only the admin verification service writes it** |
| verified_at | timestamptz null | |
| is_accepting_bookings, auto_accept | bool | |
| min_notice_hours | smallint | CHECK ≤ 336 |
| booking_horizon_days | smallint | CHECK 1–180 |
| buffer_minutes | smallint | CHECK ≤ 120 |
| rating_avg, rating_count | numeric(3,2) null, int | denormalised from published reviews by `reviews.services` |
| commission_bps | int null | Admin-only commission override in basis points (≤ 10 000); null = `PLATFORM_FEE_BPS` |

M2M: `categories`, `skills` (through `mentors_mentorskill`, UNIQUE (mentor, skill)) and `languages`. Indexes on `verification_status` and `country`.

**Publicly visible** means `verification_status = 'approved'` and `users_user.is_active`.

### Other mentor tables
| Table | Key columns | Constraints |
|---|---|---|
| `mentors_mentorexperience` | mentor_id, kind (work/education), title, organization, start_date, end_date null, description | CHECK end ≥ start |
| `mentors_mentorservice` | mentor_id, title, description, duration_minutes, price_cents, currency, is_active | CHECK duration ∈ {15,30,45,60,90,120,180}; price ≤ 1,000,000; currency `^[A-Z]{3}$`; index (mentor, is_active) |
| `mentors_availabilityrule` | mentor_id, weekday (0=Mon), start_time, end_time, **timezone** (IANA, kept in sync with the profile) | CHECK weekday ≤ 6, end > start |
| `mentors_availabilityexception` | mentor_id, start_at, end_at (timestamptz), status (`available` \| `unavailable`), note | CHECK end > start; index (mentor, start_at) |
| `mentors_verificationrequest` | mentor_id, status, evidence_note, submitted_at, reviewed_by_id, reviewed_at, decision_reason | partial UNIQUE (mentor) WHERE status = 'pending' |

Availability only describes *when* a mentor can be booked. Double-booking is prevented on `bookings_booking`, below.

## bookings

### `bookings_booking`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| student_id → user, mentor_id → mentorprofile, service_id → mentorservice | | all `PROTECT` |
| service_title, duration_minutes, price_cents, currency | | **snapshot at booking time**, from the server |
| start_at, end_at | timestamptz | CHECK end > start |
| blocked_until | timestamptz | end + mentor buffer; CHECK ≥ end_at |
| status | varchar(20) | `pending_payment`, `requested`, `confirmed`, `completed`, `declined`, `cancelled`, `expired` (CHECK) |
| student_note, meeting_url | | meeting URL is only returned when confirmed |
| hold_expires_at, respond_by, confirmed_at, completed_at, cancelled_at | timestamptz null | |
| cancelled_by_id, cancellation_reason, refund_outcome | | refund_outcome ∈ `""`, `not_charged`, `full_refund`, `no_refund` |

**Overlap prevention (database-enforced):**
```sql
EXCLUDE USING gist (mentor_id WITH =, tstzrange(start_at, blocked_until, '[)') WITH &&)
  WHERE (status IN ('pending_payment','requested','confirmed'));   -- booking_no_mentor_overlap
EXCLUDE USING gist (student_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
  WHERE (status IN ('pending_payment','requested','confirmed'));   -- booking_no_student_overlap
```
Indexes: (student, start_at), (mentor, start_at), (status, hold_expires_at), (status, respond_by).

### `bookings_bookingevent` (append-only)
bigint id, booking_id, from_status, to_status, actor_id (null = system), note, created_at.

## payments
See [PAYMENTS.md](PAYMENTS.md) for the workflow and accounting rules.

| Table | Key columns | Constraints |
|---|---|---|
| `payments_payment` | booking_id (PROTECT), provider, **livemode**, checkout_reference UNIQUE null, checkout_url, checkout_expires_at, provider_reference UNIQUE null, amount_cents, currency, **commission_bps, platform_fee_cents, mentor_share_cents** (snapshot at checkout), provider_fee_cents null, status (`created`, `failed`, `authorized`, `captured`, `cancelled`), refund_status (`none`, `pending`, `partial`, `full`, `failed`), refunded_amount_cents (sum of succeeded refunds), dispute_status (`none`, `open`, `won`, `lost`), authorized_at, captured_at, failure_code | CHECK amount > 0; commission_bps ≤ 10 000; fee ≤ amount; **fee = amount − mentor_share**; refunded ≤ amount; partial UNIQUE (booking) WHERE status ∈ (created, failed, authorized, captured); index (status, livemode) |
| `payments_refund` | payment_id (PROTECT), amount_cents, commission_reversed_cents, mentor_share_reversed_cents, reason (`student_cancellation`, `mentor_cancellation`, `admin`, `dispute_lost`), status (`pending`, `succeeded`, `failed`), provider_reference UNIQUE null, initiated_by_id, note, failure_code | CHECK amount > 0; **amount = commission_reversed + mentor_share_reversed** |
| `payments_webhookevent` | provider, event_id, event_type, object_reference, livemode, received_at, processed_at, outcome | **UNIQUE (provider, event_id)**: idempotent processing. No payload stored |
| `payments_payout` | mentor_id (PROTECT), amount_cents, currency, status (`pending`, `paid`, `failed`, `cancelled`), method, external_reference, created_by_id, paid_at | CHECK amount > 0. Manual records only |

- No card data, CVCs, credentials or webhook payloads are stored; only provider references, amounts and decline/error codes.
- Payment status changes only through `payments.services` (verified webhooks or authenticated provider API responses). No API can set it, and all payment tables are read-only in Django admin.

## notifications
`notifications_emailnotification` has the columns id (uuid), **dedupe_key UNIQUE**, template, recipient_id (SET NULL), context (jsonb; one-time links removed after sending), status (`queued`, `sent`, `failed`, `skipped`), attempts, last_error (exception type only), sent_at and timestamps. See [NOTIFICATIONS.md](NOTIFICATIONS.md).

## reviews
`reviews_review` has the columns booking_id **UNIQUE** (PROTECT), student_id, mentor_id, rating, comment, status (`published` / `hidden`), hidden_reason and timestamps.
- Constraints: CHECK rating 1–5 and a valid status.
- Index: (mentor, status, -created_at).
- Eligibility (the booking is completed and the reviewer is its student) is enforced in `reviews.services`.

## moderation
`moderation_report` has the columns reporter_id, target_type (`review` / `mentor_profile` / `booking` / `user`), target_id (uuid), target_label, reason, details, status (`open` / `in_review` / `actioned` / `dismissed`), resolved_by_id, resolution_note and resolved_at.
- Constraint: partial UNIQUE (reporter, target_type, target_id) for unresolved reports.
- Index: (status, created_at).

## common
`common_auditlogentry` is append-only. Its columns are bigint id, actor_id, action (e.g. `mentor.verification.approved`, `user.suspended`, `report.actioned`, `review.hidden`, `booking.cancelled_by_admin`, `payment.refund.created`, `payment.refund.failed`, `payment.dispute.lost`; actor null = system), target_type, target_id, metadata (jsonb, no secrets), ip_address and created_at.

## Framework tables
`django_session`, `django_cache` (created with `createcachetable`; used for rate limiting), `django_content_type`, `auth_permission` / `auth_group` (Django admin only), and `django_admin_log`.
