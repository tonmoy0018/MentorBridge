from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.bookings.models import ACTIVE_STATUSES, BookingStatus
from apps.common.serializers import MoneySerializer, money
from apps.mentors.models import ALLOWED_DURATIONS, MAX_PRICE_CENTS, SessionFormat

from .models import MAX_CAPACITY, MIN_CAPACITY, Seminar, SeminarStatus


def with_seats(qs):
    return qs.annotate(taken=Count("registrations", filter=Q(registrations__status__in=ACTIVE_STATUSES)))


class SeminarServiceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()


class SeminarSerializer(serializers.ModelSerializer):
    """Public view of a seminar: no attendee details, no exact meeting place. Expects `with_seats()`."""

    format = serializers.ChoiceField(choices=SessionFormat.choices, read_only=True)
    price = serializers.SerializerMethodField(help_text="Per seat.")
    seats_left = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()

    class Meta:
        model = Seminar
        fields = [
            "id",
            "title",
            "description",
            "service",
            "start_at",
            "end_at",
            "duration_minutes",
            "capacity",
            "seats_left",
            "price",
            "format",
            "in_person_area",
        ]
        read_only_fields = fields

    @extend_schema_field(MoneySerializer)
    def get_price(self, obj):
        return money(obj.price_cents, obj.currency)

    def _taken(self, obj) -> int:
        taken = getattr(obj, "taken", None)
        return obj.registrations.filter(status__in=ACTIVE_STATUSES).count() if taken is None else taken

    def get_seats_left(self, obj) -> int:
        return max(obj.capacity - self._taken(obj), 0)

    @extend_schema_field(SeminarServiceSerializer)
    def get_service(self, obj):
        return {"id": str(obj.service_id), "title": obj.service.title}


class SeminarAttendeeSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()
    display_name = serializers.CharField()
    status = serializers.ChoiceField(choices=BookingStatus.choices)


class MentorSeminarSerializer(SeminarSerializer):
    """The mentor's own view, with private details and who's coming."""

    status = serializers.ChoiceField(choices=SeminarStatus.choices, read_only=True)
    seats_taken = serializers.SerializerMethodField()
    attendees = serializers.SerializerMethodField()

    class Meta(SeminarSerializer.Meta):
        fields = [
            *SeminarSerializer.Meta.fields,
            "seats_taken",
            "meeting_place",
            "meeting_url",
            "status",
            "cancellation_reason",
            "attendees",
        ]
        read_only_fields = fields

    def get_seats_taken(self, obj) -> int:
        return self._taken(obj)

    @extend_schema_field(SeminarAttendeeSerializer(many=True))
    def get_attendees(self, obj):
        seats = [
            b for b in obj.registrations.all() if b.status in (*ACTIVE_STATUSES, BookingStatus.COMPLETED)
        ]
        return [
            {"booking_id": str(b.pk), "display_name": b.student.full_name, "status": b.status} for b in seats
        ]


class SeminarWriteSerializer(serializers.Serializer):
    service_id = serializers.UUIDField()
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    start_at = serializers.DateTimeField()
    duration_minutes = serializers.ChoiceField(choices=ALLOWED_DURATIONS)
    capacity = serializers.IntegerField(min_value=MIN_CAPACITY, max_value=MAX_CAPACITY)
    price_cents = serializers.IntegerField(min_value=0, max_value=MAX_PRICE_CENTS)
    currency = serializers.CharField(min_length=3, max_length=3, required=False)
    format = serializers.ChoiceField(choices=SessionFormat.choices, required=False)
    in_person_area = serializers.CharField(max_length=120, required=False, allow_blank=True)
    meeting_place = serializers.CharField(max_length=300, required=False, allow_blank=True)
    meeting_url = serializers.URLField(max_length=300, required=False, allow_blank=True)

    def validate_meeting_url(self, value):
        from apps.mentors.serializers import _https_url  # mentors.serializers imports this module

        return _https_url(value, message="Enter a secure (https://) meeting link.") if value else value


class AdminSeminarSerializer(MentorSeminarSerializer):
    """Admin list: everything but the exact place (revealed only through the audited endpoint)."""

    class Meta(MentorSeminarSerializer.Meta):
        fields = [f for f in MentorSeminarSerializer.Meta.fields if f != "meeting_place"]
        read_only_fields = fields
