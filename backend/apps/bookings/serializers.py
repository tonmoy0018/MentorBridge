from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.common.serializers import MoneySerializer, money

from .models import Booking, BookingEvent, BookingStatus


class BookingPartySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    display_name = serializers.CharField()
    avatar_url = serializers.URLField(allow_null=True)


class BookingMentorSerializer(BookingPartySerializer):
    slug = serializers.CharField()
    headline = serializers.CharField()


class BookingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingEvent
        fields = ["from_status", "to_status", "note", "created_at"]


class BookingSerializer(serializers.ModelSerializer):
    """A booking as seen by its student, its mentor or an admin. No contact details are exposed."""

    price = serializers.SerializerMethodField()
    mentor = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    meeting_url = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "status",
            "start_at",
            "end_at",
            "service_title",
            "duration_minutes",
            "price",
            "student_note",
            "meeting_url",
            "mentor",
            "student",
            "hold_expires_at",
            "respond_by",
            "confirmed_at",
            "completed_at",
            "cancelled_at",
            "cancellation_reason",
            "refund_outcome",
            "has_review",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(MoneySerializer)
    def get_price(self, obj):
        return money(obj.price_cents, obj.currency)

    def _avatar(self, mentor):
        if not mentor.avatar:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(mentor.avatar.url) if request else mentor.avatar.url

    @extend_schema_field(BookingMentorSerializer)
    def get_mentor(self, obj):
        mentor = obj.mentor
        return {
            "id": str(mentor.pk),
            "slug": mentor.slug,
            "display_name": mentor.user.full_name,
            "headline": mentor.current_title or mentor.headline,
            "avatar_url": self._avatar(mentor),
        }

    @extend_schema_field(BookingPartySerializer)
    def get_student(self, obj):
        return {"id": str(obj.student_id), "display_name": obj.student.full_name, "avatar_url": None}

    has_review = serializers.SerializerMethodField(help_text="Whether the student has reviewed this booking.")

    def get_has_review(self, obj) -> bool:
        try:
            return obj.review is not None
        except ObjectDoesNotExist:
            return False

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_meeting_url(self, obj):
        # Only revealed for confirmed sessions. Falls back to the mentor's current default link if
        # none was recorded when the booking was accepted.
        if obj.status != BookingStatus.CONFIRMED:
            return None
        return obj.meeting_url or obj.mentor.meeting_url or None


class BookingDetailSerializer(BookingSerializer):
    events = BookingEventSerializer(many=True, read_only=True)

    class Meta(BookingSerializer.Meta):
        fields = [*BookingSerializer.Meta.fields, "events"]
        read_only_fields = fields


class CreateBookingSerializer(serializers.Serializer):
    """The client chooses a service and a start time. Price and duration always come from the server."""

    service_id = serializers.UUIDField()
    start_at = serializers.DateTimeField()
    student_note = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class BookingListQuerySerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=["upcoming", "past", "all"], required=False, default="all")
    status = serializers.ListField(
        child=serializers.ChoiceField(choices=BookingStatus.choices), required=False
    )
