from django.core.management.base import BaseCommand

from apps.bookings.services import expire_due


class Command(BaseCommand):
    help = "Expire lapsed payment holds and unanswered booking requests. Safe to run repeatedly."

    def handle(self, *args, **options):
        count = expire_due()
        self.stdout.write(f"Expired {count} booking(s).")
