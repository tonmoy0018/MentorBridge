"""Session-bundle operations. Views stay thin; every write goes through here."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import Conflict, DomainError, ServiceUnavailable
from apps.mentors.models import MentorProfile, MentorService, SessionFormat

from .models import MentorPackage, PackagePurchase, PurchaseStatus

logger = logging.getLogger(__name__)


def create_package(mentor: MentorProfile, data: dict) -> MentorPackage:
    data = dict(data)
    service = MentorService.objects.filter(pk=data.pop("service_id"), mentor=mentor, is_active=True).first()
    if service is None:
        raise ValidationError({"service_id": "Choose one of your active services."})
    if service.packages.filter(session_count=data["session_count"]).exists():
        raise ValidationError(
            {"session_count": "This session already has an option with that many sessions."}
        )
    return MentorPackage.objects.create(mentor=mentor, service=service, **data)


def update_package(package: MentorPackage, data: dict) -> MentorPackage:
    """Edits apply to new purchases only; existing purchases keep their snapshotted terms."""
    data = dict(data)
    data.pop("service_id", None)  # an option belongs to its session for good
    count = data.get("session_count", package.session_count)
    if package.service.packages.exclude(pk=package.pk).filter(session_count=count).exists():
        raise ValidationError(
            {"session_count": "This session already has an option with that many sessions."}
        )
    for field, value in data.items():
        setattr(package, field, value)
    package.save()
    return package


def delete_package(package: MentorPackage) -> None:
    if package.purchases.exists():
        raise Conflict("package_in_use", "Students have bought this option. Hide it instead of deleting it.")
    package.delete()


def _activate(purchase: PackagePurchase, now) -> None:
    purchase.status = PurchaseStatus.ACTIVE
    purchase.expires_at = now + timedelta(days=purchase.package.validity_days)
    purchase.save(update_fields=["status", "expires_at", "updated_at"])


def activate_after_payment(purchase: PackagePurchase) -> bool:
    """Called when the provider confirms payment. Returns False if the purchase was closed meanwhile."""
    purchase = PackagePurchase.objects.select_for_update().select_related("package").get(pk=purchase.pk)
    if purchase.status == PurchaseStatus.ACTIVE:
        return True
    if purchase.status != PurchaseStatus.PENDING_PAYMENT:
        return False
    _activate(purchase, timezone.now())
    logger.info("Package purchase %s paid and active", purchase.pk)
    return True


def close_unpaid(purchase: PackagePurchase) -> None:
    """The checkout expired or was abandoned: nothing was charged and the bundle is never usable."""
    updated = PackagePurchase.objects.filter(pk=purchase.pk, status=PurchaseStatus.PENDING_PAYMENT).update(
        status=PurchaseStatus.CANCELLED, updated_at=timezone.now()
    )
    if updated:
        logger.info("Package purchase %s closed unpaid", purchase.pk)


def purchase_package(*, student, package_id, session_format: str | None = None):
    """
    Buy a bundle in the chosen format. Returns (purchase, checkout_url). A paid bundle starts
    `pending_payment` and becomes usable only once the provider confirms the payment; a repeated
    request reuses the open checkout. A bundle that costs nothing is active at once.
    """
    from apps.payments.services import start_checkout_for_purchase

    now = timezone.now()
    with transaction.atomic():
        package = (
            MentorPackage.objects.select_for_update()
            .select_related("mentor__user", "service")
            .filter(pk=package_id)
            .first()
        )
        if (
            package is None
            or not package.is_active
            or not package.service.is_active
            or not package.mentor.is_publicly_visible
        ):
            raise DomainError("not_found", "Package not found.", status_code=404)
        if not package.mentor.is_accepting_bookings:
            raise Conflict("not_accepting_bookings", "This mentor isn't accepting new bookings right now.")
        if settings.REQUIRE_VERIFIED_EMAIL and not student.email_verified:
            raise DomainError(
                "email_not_verified", "Verify your email address before booking.", status_code=403
            )
        service = package.service
        session_format = session_format or (
            SessionFormat.ONLINE if service.online else SessionFormat.IN_PERSON
        )
        if not service.offers(session_format):
            raise Conflict(
                "format_unavailable",
                f"This session isn't offered {SessionFormat(session_format).label.lower()}.",
            )
        price = package.price_cents(session_format)
        if price > 0 and not settings.PAYMENTS_ENABLED:
            raise ServiceUnavailable(
                "payments_unavailable", "Paid sessions can't be booked until online payment is available."
            )

        mine = PackagePurchase.objects.filter(student=student, package=package)
        pending = mine.filter(status=PurchaseStatus.PENDING_PAYMENT, format=session_format).first()
        if pending is None:
            # One unfinished copy at a time: use (or let expire) the one you have first.
            for held in mine.filter(status=PurchaseStatus.ACTIVE, expires_at__gt=now):
                if held.used_count() < held.session_count:
                    raise Conflict("package_already_held", "You already have this option with sessions left.")
            # Switching format abandons any other unpaid attempt.
            for other in mine.filter(status=PurchaseStatus.PENDING_PAYMENT):
                close_unpaid(other)
            pending = PackagePurchase.objects.create(
                student=student,
                package=package,
                mentor=package.mentor,
                service=service,
                format=session_format,
                title=package.title,
                session_count=package.session_count,
                duration_minutes=service.duration_minutes,
                price_cents=price,
                currency=service.currency,
                status=PurchaseStatus.PENDING_PAYMENT,
            )
            logger.info("Package purchase %s started for package %s", pending.pk, package.pk)
        if price == 0:
            _activate(pending, now)
            return pending, None
    payment = start_checkout_for_purchase(pending, student=student)
    return pending, payment.checkout_url


def lock_for_booking(*, student, purchase_id, service: MentorService, start_at, now) -> PackagePurchase:
    """Lock a purchase and check it can pay for one more session. Call inside a transaction."""
    purchase = PackagePurchase.objects.select_for_update().filter(pk=purchase_id, student=student).first()
    if purchase is None:
        raise DomainError("not_found", "Package not found.", status_code=404)
    if purchase.status != PurchaseStatus.ACTIVE:
        raise Conflict("package_not_active", "This package isn't paid for or is no longer active.")
    if purchase.service_id != service.pk:
        raise Conflict("package_mismatch", "This package is for a different session.")
    if purchase.expires_at <= now:
        raise Conflict("package_expired", "This package has expired.")
    if start_at > purchase.expires_at:
        raise Conflict("package_expires_first", "Choose a time before your package expires.")
    if purchase.used_count() >= purchase.session_count:
        raise Conflict("package_used_up", "You've used every session in this package.")
    return purchase
