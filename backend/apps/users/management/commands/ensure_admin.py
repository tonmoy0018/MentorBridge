import os

from django.core.management.base import BaseCommand, CommandError

from apps.users.models import User


class Command(BaseCommand):
    help = (
        "Create an administrator from DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD if it doesn't "
        "exist. Idempotent; never changes an existing account. Intended for dev and test stacks."
    )

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip().lower()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not email or not password:
            raise CommandError("Set DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD.")
        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(f"Admin {email} already exists.")
            return
        User.objects.create_superuser(email=email, password=password, first_name="E2E", last_name="Admin")
        self.stdout.write(f"Created admin {email}.")
