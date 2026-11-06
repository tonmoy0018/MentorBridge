# Notifications

Transactional email: what is sent, when, and how duplicates and private data are kept out.

> **Status (2026-11-06):** implemented and tested. In development, email goes to Mailpit (http://localhost:8025). **No production email provider is configured yet.**

## 1. How it works

```python
notify("booking_confirmed_student", user, context, dedupe_key=f"booking.confirmed:{booking.pk}:student")
```

1. `notify()` is called **inside the transaction** that made the change. It inserts an `EmailNotification` row with a unique `dedupe_key`.
   - If the change rolls back, the row and the email disappear with it.
   - If the key already exists (the same event processed again, e.g. a duplicate webhook or a scheduler re-run), nothing happens.
2. **After commit**, `deliver()` renders the template and sends it. The row becomes `sent`, `failed` (with the exception *type* only) or `skipped` (recipient deactivated).
3. The scheduler runs `manage.py send_notifications` every minute. It retries `failed` rows up to **3 attempts**, plus rows stuck in `queued` for more than 5 minutes.

Templates live in `backend/templates/notifications/email/<name>.subject.txt` and `<name>.txt`. They're plain text and rendered by a separate Django template engine (`email_text`) with HTML autoescaping **off**, so links aren't mangled (`&amp;`). Times are shown in the recipient's time zone.

## 2. Emails

| Template | To | Trigger | Dedupe key |
|---|---|---|---|
| `account_verification` | New user | Registration, resend | unique per request |
| `password_reset` | User | Reset requested (only for existing accounts) | unique per request |
| `mentor_verification_approved` / `_rejected` | Mentor | Admin decision | `mentor.verification.<status>:<request id>` |
| `booking_requested_mentor` | Mentor | Free request created, or paid booking authorised | `booking.requested:<booking>` |
| `booking_confirmed_student` / `_mentor` | Both | Accepted / auto-accepted | `booking.confirmed:<booking>:<role>` |
| `booking_declined_student` | Student | Mentor declines | `booking.declined:<booking>` |
| `booking_cancelled` | The party who didn't cancel (both, for admin cancellations) | Cancellation, with refund wording for the student | `booking.cancelled:<booking>:<role>` |
| `booking_expired_student` | Student | Request expired unanswered | `booking.expired:<booking>` |
| `session_reminder` | Both | Confirmed session starts within 24 h (`send_session_reminders`, every minute) | `booking.reminder:<booking>:<role>` |
| `payment_failed` | Student | Card declined (webhook) | `payment.failed:<provider event id>` |
| `payment_released` | Student | Authorisation released because the booking was no longer available | `payment.released:<payment>` |
| `refund_initiated` / `refund_succeeded` / `refund_failed` | Student | Refund lifecycle | `refund.<state>:<refund>` |

## 3. Privacy

- **Logs** carry the notification id, template and dedupe key (internal ids only). They never carry addresses, names or content. A test asserts that addresses, last names and service titles never appear in logs.
- **`last_error`** stores the exception class only, e.g. `SMTPException`, never the server's message (which often echoes the address).
- **One-time links** (verification, password reset) are removed from the stored context as soon as the email is sent. Django admin never shows the stored context.
- **The admin email log** (`GET /admin/notifications/`, **Admin → Emails**) shows template, status, attempts and the recipient's display name. It shows no address and no content.

## 4. Configuration

| Variable | Default (dev) | Meaning |
|---|---|---|
| `EMAIL_BACKEND` | SMTP | Django email backend |
| `EMAIL_HOST` / `EMAIL_PORT` | `mailpit` / 1025 | SMTP server |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | empty | SMTP credentials (secrets: environment only) |
| `EMAIL_USE_TLS` | false | TLS for SMTP |
| `DEFAULT_FROM_EMAIL` | `MentorBridge <no-reply@mentorbridge.local>` | Sender |
| `FRONTEND_URL` | `http://localhost:3000` | Base for links in emails |

**For production:** choose a provider (e.g. Postmark, SES or SendGrid), set the SMTP variables, and configure SPF/DKIM for the sending domain. Run the scheduler commands (`expire_bookings`, `send_session_reminders`, `send_notifications`) every minute.

## 5. Tests

`backend/tests/test_notifications.py` covers:
- de-duplication, and that a rolled-back change sends nothing;
- failure recording, retries capped at 3, and the `send_notifications` retry;
- secret-link scrubbing and log hygiene;
- booking lifecycle emails and reminder idempotency;
- the admin log's privacy and permissions.

Payment and refund emails are covered in `test_payments.py`.
