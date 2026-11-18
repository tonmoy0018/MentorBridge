from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.bookings.serializers import BookingDetailSerializer, MeetingPlaceRevealSerializer
from apps.common.permissions import IsAdminRole, IsStudent
from apps.common.schema import AUTHED, E400, E404, E409, E429, errors
from apps.common.serializers import RequiredReasonSerializer
from apps.common.throttling import IPScopedThrottle
from apps.mentors.views import ME, MentorSelfMixin, _validation

from . import services
from .models import Seminar
from .serializers import (
    AdminSeminarSerializer,
    MentorSeminarSerializer,
    SeminarSerializer,
    SeminarWriteSerializer,
    with_seats,
)


def _mentor_seminars(mentor):
    seats = Booking.objects.select_related("student").order_by("created_at")
    return with_seats(
        Seminar.objects.filter(mentor=mentor)
        .select_related("service")
        .prefetch_related(Prefetch("registrations", queryset=seats))
    ).order_by("-start_at")


class MySeminarListView(MentorSelfMixin, APIView):
    @extend_schema(
        tags=ME,
        summary="List my group seminars",
        responses={200: MentorSeminarSerializer(many=True), **AUTHED},
    )
    def get(self, request):
        return Response(MentorSeminarSerializer(_mentor_seminars(self.get_mentor()), many=True).data)

    @extend_schema(
        tags=ME,
        summary="Schedule a group seminar",
        description="A fixed-time session of one of your services for several students. "
        "The time must be free.",
        request=SeminarWriteSerializer,
        responses={201: MentorSeminarSerializer, **errors(E400, AUTHED, E409)},
    )
    def post(self, request):
        serializer = SeminarWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mentor = self.get_mentor()
        try:
            seminar = services.create_seminar(mentor, serializer.validated_data)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(
            MentorSeminarSerializer(_mentor_seminars(mentor).get(pk=seminar.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class MySeminarDetailView(MentorSelfMixin, APIView):
    @extend_schema(
        tags=ME,
        summary="Update a group seminar",
        description="Once students have registered, the time, length, price and format can't change.",
        request=SeminarWriteSerializer,
        responses={200: MentorSeminarSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def patch(self, request, pk):
        mentor = self.get_mentor()
        seminar = get_object_or_404(Seminar, pk=pk, mentor=mentor)
        serializer = SeminarWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_seminar(seminar, serializer.validated_data)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(MentorSeminarSerializer(_mentor_seminars(mentor).get(pk=pk)).data)


class MySeminarCancelView(MentorSelfMixin, APIView):
    @extend_schema(
        tags=ME,
        summary="Cancel a group seminar",
        description="Every seat is cancelled and refunded in full; each student gets one email.",
        request=RequiredReasonSerializer,
        responses={200: MentorSeminarSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        mentor = self.get_mentor()
        seminar = get_object_or_404(Seminar, pk=pk, mentor=mentor)
        serializer = RequiredReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_seminar(seminar, actor=request.user, reason=serializer.validated_data["reason"])
        return Response(MentorSeminarSerializer(_mentor_seminars(mentor).get(pk=pk)).data)


class MySeminarCompleteView(MentorSelfMixin, APIView):
    @extend_schema(
        tags=ME,
        summary="Mark a group seminar as completed",
        description="Confirmed seats become completed, so students can leave a review.",
        request=None,
        responses={200: MentorSeminarSerializer, **errors(AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        mentor = self.get_mentor()
        seminar = get_object_or_404(Seminar, pk=pk, mentor=mentor)
        services.complete_seminar(seminar, actor=request.user)
        return Response(MentorSeminarSerializer(_mentor_seminars(mentor).get(pk=pk)).data)


class SeminarRegisterView(APIView):
    permission_classes = [IsStudent]
    throttle_scope = "booking_create"

    def get_throttles(self):
        return [IPScopedThrottle()]

    @extend_schema(
        tags=["Seminars"],
        summary="Register for a group seminar",
        description=(
            "Free seminars: the seat is confirmed at once. Paid seminars: the seat is held "
            "(`pending_payment`) like a paid booking and confirmed when the provider confirms payment."
        ),
        request=None,
        responses={201: BookingDetailSerializer, **errors(AUTHED, E404, E409, E429)},
    )
    def post(self, request, pk):
        booking = services.register(student=request.user, seminar_id=pk)
        return Response(
            BookingDetailSerializer(booking, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AdminSeminarListView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Admin"],
        summary="Upcoming group seminars",
        responses={200: AdminSeminarSerializer(many=True), **AUTHED},
    )
    def get(self, request):
        from django.utils import timezone

        seats = Booking.objects.select_related("student").order_by("created_at")
        qs = with_seats(
            Seminar.objects.filter(start_at__gte=timezone.now() - timezone.timedelta(days=30))
            .select_related("service")
            .prefetch_related(Prefetch("registrations", queryset=seats))
        ).order_by("start_at")[:200]
        return Response(AdminSeminarSerializer(qs, many=True).data)


class AdminSeminarCancelView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Admin"],
        summary="Cancel any group seminar",
        request=RequiredReasonSerializer,
        responses={200: SeminarSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        seminar = get_object_or_404(Seminar, pk=pk)
        serializer = RequiredReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_seminar(
            seminar, actor=request.user, reason=serializer.validated_data["reason"], request=request
        )
        return Response(SeminarSerializer(with_seats(Seminar.objects.filter(pk=pk)).get()).data)


class AdminSeminarMeetingPlaceView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Admin"],
        summary="Reveal the exact place of an in-person seminar",
        description="For safety and incident handling. A reason is required and every request is recorded "
        "in the audit log (the place itself is not logged).",
        request=RequiredReasonSerializer,
        responses={200: MeetingPlaceRevealSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        from apps.bookings.services import reveal_meeting_place

        seminar = get_object_or_404(Seminar, pk=pk)
        serializer = RequiredReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = reveal_meeting_place(
            seminar, actor=request.user, reason=serializer.validated_data["reason"], request=request
        )
        return Response(MeetingPlaceRevealSerializer(result).data)
