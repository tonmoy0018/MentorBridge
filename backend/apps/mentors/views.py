from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminRole, IsMentor
from apps.common.schema import AUTHED, E400, E404, E409, errors
from apps.common.serializers import RequiredReasonSerializer

from . import selectors, services
from .models import (
    AvailabilityException,
    MentorExperience,
    MentorProfile,
    MentorService,
    VerificationRequest,
    VerificationRequestStatus,
)
from .serializers import (
    AvailabilityExceptionSerializer,
    AvailabilityQuerySerializer,
    AvailabilityResponseSerializer,
    AvailabilityRuleSerializer,
    ExperienceSerializer,
    MentorOwnProfileSerializer,
    MentorProfileUpdateSerializer,
    MentorPublicProfileSerializer,
    MentorSearchQuerySerializer,
    MentorSummarySerializer,
    ServiceSerializer,
    ServiceWriteSerializer,
    VerificationRequestSerializer,
    VerificationSubmitSerializer,
)

PUBLIC = ["Mentors"]
ME = ["Mentor self-service"]
ADMIN = ["Admin"]


# --- public ----------------------------------------------------------------------------


@extend_schema(
    tags=PUBLIC,
    summary="Search approved mentors",
    description="Only mentors approved through verification (and with an active account) are listed. "
    "`price_min`/`price_max` compare against the mentor's lowest active service price, in cents. "
    "`available_within_days` keeps mentors with an open slot in that many days.",
    parameters=[
        MentorSearchQuerySerializer,
        OpenApiParameter("page", int),
        OpenApiParameter("page_size", int),
    ],
    responses={200: MentorSummarySerializer(many=True), **E400},
)
class MentorListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = MentorSummarySerializer

    def list(self, request, *args, **kwargs):
        query = MentorSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        now = timezone.now()
        mentors = selectors.search_mentors(params)

        within = params.get("available_within_days")
        if within:
            # Availability depends on schedules and bookings, so it's evaluated in Python on the
            # filtered candidates (bounded; see docs/ARCHITECTURE.md for the scaling plan).
            candidates = list(mentors[: selectors.AVAILABILITY_FILTER_CANDIDATE_LIMIT])
            next_available = selectors.next_available_map(candidates, now)
            limit = now + timedelta(days=within)
            mentors = [m for m in candidates if next_available[m.pk] and next_available[m.pk] <= limit]
            page = self.paginate_queryset(mentors)
        else:
            page = self.paginate_queryset(mentors)
            next_available = selectors.next_available_map(list(page), now)

        serializer = self.get_serializer(
            page, many=True, context={"request": request, "next_available": next_available}
        )
        return self.get_paginated_response(serializer.data)


@extend_schema(
    tags=PUBLIC,
    summary="Get a mentor's public profile",
    description="`id` is the mentor's slug or UUID.",
    responses={200: MentorPublicProfileSerializer, **E404},
)
class MentorDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, identifier):
        qs = selectors.public_mentors().prefetch_related(
            "experiences", Prefetch("services", queryset=MentorService.objects.filter(is_active=True))
        )
        mentor = selectors.get_public_mentor(identifier, qs)
        context = {"request": request, "next_available": selectors.next_available_map([mentor])}
        return Response(MentorPublicProfileSerializer(mentor, context=context).data)


class MentorAvailabilityView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=PUBLIC,
        summary="Bookable start times",
        description="Start times (UTC) for a service between `from` and `to` (UTC dates, inclusive, at most "
        "31 days). Already respects minimum notice, booking horizon, buffers and existing bookings.",
        parameters=[
            OpenApiParameter("service", str, required=True, description="Service UUID"),
            OpenApiParameter("from", str, required=True, description="YYYY-MM-DD"),
            OpenApiParameter("to", str, required=True, description="YYYY-MM-DD"),
        ],
        responses={200: AvailabilityResponseSerializer, **errors(E400, E404)},
    )
    def get(self, request, identifier):
        mentor = selectors.get_public_mentor(identifier)
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        service = get_object_or_404(MentorService, pk=params["service"], mentor=mentor, is_active=True)

        now = timezone.now()
        window_start = max(selectors.utc_day_start(params["from"]), now)
        window_end = selectors.utc_day_start(params["to"]) + timedelta(days=1)
        slots = (
            selectors.bookable_slots(
                mentor,
                duration_minutes=service.duration_minutes,
                window_start=window_start,
                window_end=window_end,
                now=now,
            )
            if window_end > window_start
            else []
        )
        data = {
            "mentor_timezone": mentor.timezone,
            "service_id": service.pk,
            "duration_minutes": service.duration_minutes,
            "slots": slots,
        }
        return Response(AvailabilityResponseSerializer(data).data)


# --- mentor self-service ---------------------------------------------------------------


class MentorSelfMixin:
    permission_classes = [IsMentor]

    def get_mentor(self) -> MentorProfile:
        try:
            return self.request.user.mentor_profile
        except MentorProfile.DoesNotExist as exc:
            raise NotFound("Mentor profile not found.") from exc


def _validation(exc: DjangoValidationError):
    from rest_framework.exceptions import ValidationError

    return ValidationError(
        exc.message_dict if hasattr(exc, "error_dict") else {"non_field_errors": exc.messages}
    )


class MyMentorProfileView(MentorSelfMixin, APIView):
    def _out(self, mentor):
        return MentorOwnProfileSerializer(mentor, context={"request": self.request}).data

    @extend_schema(
        tags=ME, summary="Get my mentor profile", responses={200: MentorOwnProfileSerializer, **AUTHED}
    )
    def get(self, request):
        return Response(self._out(self.get_mentor()))

    @extend_schema(
        tags=ME,
        summary="Update my mentor profile",
        description="Partial update. `verification_status`, ratings and the slug are read-only.",
        request=MentorProfileUpdateSerializer,
        responses={200: MentorOwnProfileSerializer, **errors(E400, AUTHED)},
    )
    def patch(self, request):
        mentor = self.get_mentor()
        serializer = MentorProfileUpdateSerializer(mentor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_profile(mentor, serializer.validated_data, actor=request.user, request=request)
        mentor.refresh_from_db()
        return Response(self._out(mentor))


class MyMentorAvatarView(MentorSelfMixin, APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=ME,
        summary="Upload a profile photo",
        description="Multipart field `avatar`: JPEG, PNG or WebP, at most 2 MB and 4000×4000 px. "
        "The image content is checked, not just the file name.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"avatar": {"type": "string", "format": "binary"}},
            }
        },
        responses={200: MentorOwnProfileSerializer, **errors(E400, AUTHED)},
    )
    def post(self, request):
        upload = request.FILES.get("avatar")
        if upload is None:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"avatar": "Choose an image to upload."})
        mentor = self.get_mentor()
        try:
            services.set_avatar(mentor, upload)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(MentorOwnProfileSerializer(mentor, context={"request": request}).data)

    @extend_schema(tags=ME, summary="Remove my profile photo", responses={204: None, **AUTHED})
    def delete(self, request):
        services.clear_avatar(self.get_mentor())
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=ME)
class MyExperienceListView(MentorSelfMixin, generics.ListCreateAPIView):
    serializer_class = ExperienceSerializer
    pagination_class = None

    def get_queryset(self):
        return MentorExperience.objects.filter(mentor=self.get_mentor())

    def perform_create(self, serializer):
        serializer.save(mentor=self.get_mentor())


@extend_schema(tags=ME)
class MyExperienceDetailView(MentorSelfMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ExperienceSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        return MentorExperience.objects.filter(mentor=self.get_mentor())


class MyServiceListView(MentorSelfMixin, generics.ListAPIView):
    serializer_class = ServiceSerializer

    def get_queryset(self):
        return MentorService.objects.filter(mentor=self.get_mentor())

    @extend_schema(tags=ME, summary="List my services (including hidden ones)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=ME,
        summary="Create a service",
        request=ServiceWriteSerializer,
        responses={201: ServiceSerializer, **errors(E400, AUTHED)},
    )
    def post(self, request):
        serializer = ServiceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service = services.create_service(self.get_mentor(), dict(serializer.validated_data))
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(ServiceSerializer(service).data, status=status.HTTP_201_CREATED)


class MyServiceDetailView(MentorSelfMixin, APIView):
    def _get(self, pk) -> MentorService:
        # Scoped to the caller: another mentor's service is a 404.
        return get_object_or_404(MentorService, pk=pk, mentor=self.get_mentor())

    @extend_schema(
        tags=ME, summary="Get one of my services", responses={200: ServiceSerializer, **errors(AUTHED, E404)}
    )
    def get(self, request, pk):
        return Response(ServiceSerializer(self._get(pk)).data)

    @extend_schema(
        tags=ME,
        summary="Update a service",
        description="Price and duration changes apply to new bookings only.",
        request=ServiceWriteSerializer,
        responses={200: ServiceSerializer, **errors(E400, AUTHED, E404)},
    )
    def patch(self, request, pk):
        service = self._get(pk)
        serializer = ServiceWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_service(service, dict(serializer.validated_data))
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(ServiceSerializer(service).data)

    @extend_schema(
        tags=ME,
        summary="Delete a service without bookings",
        responses={204: None, **errors(AUTHED, E404, E409)},
    )
    def delete(self, request, pk):
        services.delete_service(self._get(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyAvailabilityRulesView(MentorSelfMixin, APIView):
    @extend_schema(
        tags=ME,
        summary="Get my weekly hours",
        responses={200: AvailabilityRuleSerializer(many=True), **AUTHED},
    )
    def get(self, request):
        rules = self.get_mentor().availability_rules.all()
        return Response(AvailabilityRuleSerializer(rules, many=True).data)

    @extend_schema(
        tags=ME,
        summary="Replace my weekly hours",
        description="Replaces all weekly rules atomically. Times are wall-clock times in the mentor's "
        "profile time zone. Ranges on the same weekday must not overlap.",
        request=AvailabilityRuleSerializer(many=True),
        responses={200: AvailabilityRuleSerializer(many=True), **errors(E400, AUTHED)},
    )
    def put(self, request):
        serializer = AvailabilityRuleSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        try:
            rules = services.replace_availability_rules(self.get_mentor(), serializer.validated_data)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(AvailabilityRuleSerializer(rules, many=True).data)


@extend_schema(tags=ME, summary="Date-specific availability changes")
class MyAvailabilityExceptionListView(MentorSelfMixin, generics.ListCreateAPIView):
    serializer_class = AvailabilityExceptionSerializer
    pagination_class = None

    def get_queryset(self):
        return AvailabilityException.objects.filter(mentor=self.get_mentor(), end_at__gte=timezone.now())

    def perform_create(self, serializer):
        serializer.save(mentor=self.get_mentor())


@extend_schema(tags=ME)
class MyAvailabilityExceptionDetailView(MentorSelfMixin, generics.DestroyAPIView):
    serializer_class = AvailabilityExceptionSerializer

    def get_queryset(self):
        return AvailabilityException.objects.filter(mentor=self.get_mentor())


class MyVerificationView(MentorSelfMixin, APIView):
    @extend_schema(
        tags=ME,
        summary="My latest verification request",
        responses={200: VerificationRequestSerializer, **errors(AUTHED, E404)},
    )
    def get(self, request):
        latest = self.get_mentor().verification_requests.select_related("mentor__user").first()
        if latest is None:
            raise NotFound("You haven't submitted your profile yet.")
        return Response(VerificationRequestSerializer(latest).data)

    @extend_schema(
        tags=ME,
        summary="Submit my profile for verification",
        description="Requires a complete profile. Only an administrator can approve it; mentors can never "
        "set their own verification status.",
        request=VerificationSubmitSerializer,
        responses={201: MentorOwnProfileSerializer, **errors(E400, AUTHED, E409)},
    )
    def post(self, request):
        serializer = VerificationSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mentor = self.get_mentor()
        try:
            services.submit_for_verification(
                mentor,
                evidence_note=serializer.validated_data["evidence_note"],
                actor=request.user,
                request=request,
            )
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        mentor.refresh_from_db()
        return Response(
            MentorOwnProfileSerializer(mentor, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# --- admin -----------------------------------------------------------------------------


@extend_schema(
    tags=ADMIN,
    summary="List verification requests",
    parameters=[OpenApiParameter("status", str, enum=VerificationRequestStatus.values, default="pending")],
    responses={200: VerificationRequestSerializer(many=True), **AUTHED},
)
class AdminVerificationListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = VerificationRequestSerializer

    def get_queryset(self):
        status_param = self.request.query_params.get("status", VerificationRequestStatus.PENDING)
        if status_param not in VerificationRequestStatus.values:
            status_param = VerificationRequestStatus.PENDING
        order = "submitted_at" if status_param == VerificationRequestStatus.PENDING else "-reviewed_at"
        return (
            VerificationRequest.objects.filter(status=status_param)
            .select_related("mentor__user")
            .order_by(order)
        )


class _AdminVerificationAction(APIView):
    permission_classes = [IsAdminRole]

    def _get(self, pk) -> VerificationRequest:
        return get_object_or_404(VerificationRequest, pk=pk)


class AdminVerificationApproveView(_AdminVerificationAction):
    @extend_schema(
        tags=ADMIN,
        summary="Approve a mentor",
        description="Publishes the profile and grants the Verified badge. Audit-logged.",
        request=None,
        responses={200: VerificationRequestSerializer, **errors(AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        verification = services.approve_verification(self._get(pk), actor=request.user, request=request)
        return Response(VerificationRequestSerializer(verification).data)


class AdminVerificationRejectView(_AdminVerificationAction):
    @extend_schema(
        tags=ADMIN,
        summary="Reject a mentor with feedback",
        request=RequiredReasonSerializer,
        responses={200: VerificationRequestSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        serializer = RequiredReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = services.reject_verification(
            self._get(pk), actor=request.user, reason=serializer.validated_data["reason"], request=request
        )
        return Response(VerificationRequestSerializer(verification).data)
