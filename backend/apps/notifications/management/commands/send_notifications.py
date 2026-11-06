from django.core.management.base import BaseCommand

from apps.notifications.services import retry_failed


class Command(BaseCommand):
    help = "Retry failed or stuck notification emails. Safe to run repeatedly."

    def handle(self, *args, **options):
        self.stdout.write(f"Delivered {retry_failed()} notification(s).")
