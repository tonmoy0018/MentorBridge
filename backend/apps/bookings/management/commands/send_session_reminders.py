from django.core.management.base import BaseCommand

from apps.bookings.notifications import send_session_reminders


class Command(BaseCommand):
    help = "Email both participants of confirmed sessions starting in the next 24 hours. Idempotent."

    def handle(self, *args, **options):
        self.stdout.write(f"Queued {send_session_reminders()} reminder(s).")
