from urllib.parse import urlparse

from django.conf import settings
from django_countries.serializer_fields import CountryField
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.common.serializers import MoneySerializer, money
from apps.taxonomy.models import Category, Language, Profession, Skill
from apps.taxonomy.serializers import TaxonomyItemSerializer
from apps.users.services import VALID_TIMEZONES

from .models import (
    ALLOWED_DURATIONS,
    MAX_PRICE_CENTS,
    AvailabilityException,
    MentorExperience,
    MentorProfile,
    MentorService,
    VerificationRequest,
    VerificationRequestStatus,
    VerificationStatus,
)


def _avatar_url(mentor: MentorProfile, request) -> str | None:
    if not mentor.avatar:
        return None
    url = mentor.avatar.url
    return request.build_absolute_uri(url) if request is not None else url


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MentorExperience
        fields = ["id", "kind", "title", "organization", "start_date", "end_date", "description"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date must be after the start date."})
        return attrs


class ServiceSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = MentorService
        fields = [
            "id",
            "title",
            "description",
            "duration_minutes",
            "price",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(MoneySerializer)
    def get_price(self, obj):
        return money(obj.price_cents, obj.currency)


class ServiceWriteSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=3, max_length=120)
    description = serializers.CharField(min_length=10, max_length=1000)
    duration_minutes = serializers.ChoiceField(choices=ALLOWED_DURATIONS)
    price_cents = serializers.IntegerField(min_value=0, max_value=MAX_PRICE_CENTS)
    currency = serializers.CharField(min_length=3, max_length=3, required=False)
    is_active = serializers.BooleanField(default=True)


class MentorSummarySerializer(serializers.ModelSerializer):
    """Public card data. Expects `public_mentors()` annotations and a `next_available` context map."""

    display_name = serializers.CharField(source="user.full_name")
    avatar_url = serializers.SerializerMethodField()
    profession = TaxonomyItemSerializer(allow_null=True)
    industries = TaxonomyItemSerializer(source="categories", many=True)
    skills = TaxonomyItemSerializer(many=True)
    country = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True)
    starting_price = serializers.SerializerMethodField()
    next_available_at = serializers.SerializerMethodField()

    class Meta:
        model = MentorProfile
        fields = [
            "id",
            "slug",
            "display_name",
            "headline",
            "avatar_url",
            "current_title",
            "current_company",
            "profession",
            "industries",
            "skills",
            "country",
            "city",
            "languages",
            "years_experience",
            "is_verified",
            "rating_avg",
            "rating_count",
            "starting_price",
            "next_available_at",
        ]
        read_only_fields = fields

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_avatar_url(self, obj):
        return _avatar_url(obj, self.context.get("request"))

    @extend_schema_field({"type": "string", "nullable": True, "description": "ISO 3166-1 alpha-2"})
    def get_country(self, obj):
        return obj.country.code or None

    @extend_schema_field({"type": "array", "items": {"type": "string"}, "description": "ISO 639-1 codes"})
    def get_languages(self, obj):
        return [language.code for language in obj.languages.all()]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_verified(self, obj):
        # Derived from the admin verification workflow only.
        return obj.verification_status == VerificationStatus.APPROVED

    @extend_schema_field(MoneySerializer(allow_null=True))
    def get_starting_price(self, obj):
        cents = getattr(obj, "min_price_cents", None)
        return None if cents is None else money(cents)

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_next_available_at(self, obj):
        value = self.context.get("next_available", {}).get(obj.pk)
        return serializers.DateTimeField().to_representation(value) if value else None


class MentorPublicProfileSerializer(MentorSummarySerializer):
    experiences = ExperienceSerializer(many=True)
    services = serializers.SerializerMethodField()

    class Meta(MentorSummarySerializer.Meta):
        fields = [*MentorSummarySerializer.Meta.fields, "bio", "timezone", "experiences", "services"]
        read_only_fields = fields

    @extend_schema_field(ServiceSerializer(many=True))
    def get_services(self, obj):
        services = [s for s in obj.services.all() if s.is_active]
        return ServiceSerializer(services, many=True).data


class MentorOwnProfileSerializer(serializers.ModelSerializer):
    """The authenticated mentor's full profile, including private settings."""

    profession_id = serializers.PrimaryKeyRelatedField(read_only=True, source="profession", allow_null=True)
    industry_ids = serializers.PrimaryKeyRelatedField(read_only=True, many=True, source="categories")
    skill_ids = serializers.PrimaryKeyRelatedField(read_only=True, many=True, source="skills")
    language_codes = serializers.SlugRelatedField(
        read_only=True, many=True, slug_field="code", source="languages"
    )
    country = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    verification_decision_reason = serializers.SerializerMethodField()
    experiences = ExperienceSerializer(many=True, read_only=True)
    email_verified = serializers.BooleanField(source="user.email_verified", read_only=True)
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True, read_only=True)
    commission_bps = serializers.SerializerMethodField(
        help_text="Platform commission applied to this mentor's paid sessions (1500 = 15%). Set by admins."
    )

    def get_commission_bps(self, obj) -> int:
        from apps.payments.commission import commission_bps_for

        return commission_bps_for(obj)

    class Meta:
        model = MentorProfile
        fields = [
            "id",
            "slug",
            "headline",
            "bio",
            "current_title",
            "current_company",
            "profession_id",
            "industry_ids",
            "skill_ids",
            "language_codes",
            "country",
            "city",
            "timezone",
            "years_experience",
            "linkedin_url",
            "meeting_url",
            "avatar_url",
            "verification_status",
            "verification_decision_reason",
            "is_accepting_bookings",
            "auto_accept",
            "min_notice_hours",
            "booking_horizon_days",
            "buffer_minutes",
            "experiences",
            "rating_avg",
            "rating_count",
            "email_verified",
            "commission_bps",
        ]
        read_only_fields = fields

    @extend_schema_field({"type": "string", "nullable": True})
    def get_country(self, obj):
        return obj.country.code or None

    @extend_schema_field({"type": "string", "format": "uri", "nullable": True})
    def get_avatar_url(self, obj):
        return _avatar_url(obj, self.context.get("request"))

    @extend_schema_field({"type": "string", "nullable": True})
    def get_verification_decision_reason(self, obj):
        if obj.verification_status != VerificationStatus.REJECTED:
            return None
        latest = obj.verification_requests.filter(status=VerificationRequestStatus.REJECTED).first()
        return latest.decision_reason if latest else None


def _https_url(value: str, *, host_suffix: str | None = None, message: str) -> str:
    if not value:
        return value
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise serializers.ValidationError(message)
    if host_suffix and not (host == host_suffix or host.endswith("." + host_suffix)):
        raise serializers.ValidationError(message)
    return value


class MentorProfileUpdateSerializer(serializers.ModelSerializer):
    """Fields a mentor may change. Verification status and ratings are deliberately absent."""

    profession_id = serializers.PrimaryKeyRelatedField(
        source="profession", queryset=Profession.objects.all(), allow_null=True, required=False
    )
    industry_ids = serializers.PrimaryKeyRelatedField(
        source="categories", queryset=Category.objects.filter(is_active=True), many=True, required=False
    )
    skill_ids = serializers.PrimaryKeyRelatedField(
        source="skills", queryset=Skill.objects.all(), many=True, required=False
    )
    language_codes = serializers.SlugRelatedField(
        source="languages", slug_field="code", queryset=Language.objects.all(), many=True, required=False
    )
    country = CountryField(allow_blank=True, required=False)

    class Meta:
        model = MentorProfile
        fields = [
            "headline",
            "bio",
            "current_title",
            "current_company",
            "profession_id",
            "industry_ids",
            "skill_ids",
            "language_codes",
            "country",
            "city",
            "timezone",
            "years_experience",
            "linkedin_url",
            "meeting_url",
            "is_accepting_bookings",
            "auto_accept",
            "min_notice_hours",
            "booking_horizon_days",
            "buffer_minutes",
        ]
        extra_kwargs = {"bio": {"max_length": 2000}}

    def validate_industry_ids(self, value):
        if len(set(value)) > 3:
            raise serializers.ValidationError("Choose up to 3 industries.")
        return list(set(value))

    def validate_skill_ids(self, value):
        if len(set(value)) > 10:
            raise serializers.ValidationError("Choose up to 10 skills.")
        return list(set(value))

    def validate_language_codes(self, value):
        return list(set(value))

    def validate_timezone(self, value):
        if value not in VALID_TIMEZONES:
            raise serializers.ValidationError("Choose a valid IANA time zone, e.g. Europe/London.")
        return value

    def validate_linkedin_url(self, value):
        return _https_url(
            value, host_suffix="linkedin.com", message="Enter a LinkedIn profile URL starting with https://"
        )

    def validate_meeting_url(self, value):
        return _https_url(value, message="Enter a secure (https://) meeting link.")


class AvailabilityRuleSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    end_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        return attrs


class AvailabilityExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityException
        fields = ["id", "start_at", "end_at", "status", "note"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["end_at"] <= attrs["start_at"]:
            raise serializers.ValidationError({"end_at": "End must be after start."})
        if (attrs["end_at"] - attrs["start_at"]).days > 31:
            raise serializers.ValidationError({"end_at": "Exceptions can span at most 31 days."})
        return attrs


class AvailabilityQuerySerializer(serializers.Serializer):
    service = serializers.UUIDField()
    to = serializers.DateField()

    def get_fields(self):
        # `from` is a Python keyword, so it can't be declared as a class attribute.
        return {**super().get_fields(), "from": serializers.DateField()}

    def validate(self, attrs):
        if attrs["to"] < attrs["from"]:
            raise serializers.ValidationError({"to": "`to` must be on or after `from`."})
        if (attrs["to"] - attrs["from"]).days >= settings.AVAILABILITY_MAX_RANGE_DAYS:
            raise serializers.ValidationError(
                {"to": f"Ask for at most {settings.AVAILABILITY_MAX_RANGE_DAYS} days."}
            )
        return attrs


class AvailabilityResponseSerializer(serializers.Serializer):
    mentor_timezone = serializers.CharField()
    service_id = serializers.UUIDField()
    duration_minutes = serializers.IntegerField()
    slots = serializers.ListField(child=serializers.DateTimeField())


class VerificationMentorSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="user.full_name")
    country = serializers.SerializerMethodField()

    class Meta:
        model = MentorProfile
        fields = [
            "id",
            "slug",
            "display_name",
            "headline",
            "current_title",
            "current_company",
            "linkedin_url",
            "years_experience",
            "country",
        ]

    @extend_schema_field({"type": "string", "nullable": True})
    def get_country(self, obj):
        return obj.country.code or None


class VerificationRequestSerializer(serializers.ModelSerializer):
    mentor = VerificationMentorSerializer(read_only=True)

    class Meta:
        model = VerificationRequest
        fields = ["id", "status", "evidence_note", "submitted_at", "reviewed_at", "decision_reason", "mentor"]
        read_only_fields = fields


class VerificationSubmitSerializer(serializers.Serializer):
    evidence_note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class MentorSearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=100, required=False, allow_blank=True)
    industry = serializers.ListField(child=serializers.SlugField(max_length=80), required=False)
    profession = serializers.SlugField(max_length=80, required=False)
    skill = serializers.ListField(child=serializers.SlugField(max_length=80), required=False)
    country = serializers.RegexField(r"^[A-Za-z]{2}$", required=False)
    language = serializers.RegexField(r"^[a-z]{2,3}$", required=False)
    price_min = serializers.IntegerField(min_value=0, required=False, help_text="Cents")
    price_max = serializers.IntegerField(min_value=0, required=False, help_text="Cents")
    available_within_days = serializers.IntegerField(min_value=1, max_value=60, required=False)
    ordering = serializers.ChoiceField(
        choices=["relevance", "min_price_cents", "-min_price_cents", "-rating_avg", "-years_experience"],
        required=False,
    )

    def validate_country(self, value):
        return value.upper()
