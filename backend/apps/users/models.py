import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone as dj_timezone


class Role(models.TextChoices):
    STUDENT = "student", "Student"
    MENTOR = "mentor", "Mentor"
    ADMIN = "admin", "Admin"


class UserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def normalize_email_address(email: str) -> str:
        # Emails are compared case-insensitively; store them lower-cased.
        return (email or "").strip().lower()

    def get_by_natural_key(self, username):
        return self.get(email__iexact=self.normalize_email_address(username))

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_email_address(email), **extra)
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", Role.STUDENT)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        if extra["role"] == Role.ADMIN:
            extra["is_staff"] = True
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(role=Role.ADMIN, is_staff=True, is_superuser=True)
        extra.setdefault("email_verified_at", dj_timezone.now())
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Account for every person: students, mentors and admins (one role per account).
    `is_active=False` means suspended: the auth backend then refuses both login and
    existing sessions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)
    timezone = models.CharField(max_length=64, default="UTC")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=dj_timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="users_user_email_ci_unique"),
            models.CheckConstraint(condition=models.Q(role__in=Role.values), name="users_user_role_valid"),
        ]
        indexes = [models.Index(fields=["role", "is_active"])]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def short_name(self) -> str:
        """Privacy-friendly public name, e.g. "Jordan L."."""
        initial = f" {self.last_name[:1]}." if self.last_name else ""
        return f"{self.first_name}{initial}".strip()

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None
