import uuid

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import LargePagination
from apps.common.permissions import IsAdminRole, IsMentor, IsStudent, IsStudentOrMentor
from apps.common.schema import AUTHED, E400, E404, E409, E429, errors
from apps.common.serializers import ReasonSerializer, RequiredReasonSerializer
from apps.common.throttling import IPScopedThrottle
from apps.payments.serializers import CheckoutSerializer
from apps.users.models import Role

from . import services
from .models import ACTIVE_STATUSES, Booking, BookingStatus
from .serializers import (
    AcceptBookingSerializer,
    BookingDetailSerializer,
    BookingListQuerySerializer,
    BookingSerializer,
    CreateBookingSerializer,
    MeetingLinkSerializer,
    MeetingPlaceRevealSerializer,
    MeetingPlaceSerializer,
)

TAG = ["Bookings"]


def bookings_for(user):
    """Bookings the user takes part in. Anything else is invisible (404), not forbidden."""
    base = Booking.objects.select_related("mentor__user", "student", "review", "package_purchase", "seminar")
    if user.role == Role.MENTOR:
        # Seminar seats are managed per seminar (attendee list), not as individual bookings.
        return base.filter(mentor__user=user, seminar__isnull=True)
    return base.filter(student=user)


class BookingListCreateView(generics.GenericAPIView):
    serializer_class = BookingSerializer
    pagination_class = LargePagination

    def get_permissions(self):
        return [IsStudent()] if self.request.method == "POST" else [IsStudentOrMentor()]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "booking_create"
            return [IPScopedThrottle()]
        return super().get_throttles()

    @extend_schema(
        tags=TAG,
        summary="List my bookings",
        description="Students see their bookings; mentors see bookings with them. `scope=upcoming` returns "
        "active bookings that haven't ended; `past` returns ended or closed ones.",
        parameters=[
            BookingListQuerySerializer,
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={200: BookingSerializer(many=True), **errors(E400, AUTHED)},
    )
    def get(self, request):
        query = BookingListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        now = timezone.now()
        qs = bookings_for(request.user)
        if params["scope"] == "upcoming":
            qs = qs.filter(status__in=ACTIVE_STATUSES, end_at__gte=now).order_by("start_at")
        elif params["scope"] == "past":
            qs = qs.filter(Q(end_at__lt=now) | ~Q(status__in=ACTIVE_STATUSES)).order_by("-start_at")
        else:
            qs = qs.order_by("start_at")
        if statuses := params.get("status"):
            qs = qs.filter(status__in=statuses)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(
            BookingSerializer(page, many=True, context={"request": request}).data
        )

    @extend_schema(
        tags=TAG,
        summary="Book a session",
        description=(
            "Creates a booking for an open slot (see `GET /mentors/{id}/availability/`). The slot is "
            "re-validated inside a transaction; overlapping bookings are rejected by the database.\n\n"
            "* Free services → `requested` (or `confirmed` if the mentor auto-accepts).\n"
            "* Paid services → `pending_payment`, held for `BOOKING_HOLD_MINUTES`. It only advances when "
            "the payment provider confirms payment server-side (not yet available: holds expire).\n"
            "* `format=in_person` adds the service's in-person extra to the price.\n"
            "* `package_purchase_id` → paid by the package (price 0), in the package's format."
        ),
        request=CreateBookingSerializer,
        responses={201: BookingDetailSerializer, **errors(E400, AUTHED, E404, E409, E429)},
    )
    def post(self, request):
        serializer = CreateBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = services.create_booking(
            student=request.user,
            service_id=data["service_id"],
            start_at=data["start_at"],
            student_note=data["student_note"],
            session_format=data.get("format"),
            package_purchase_id=data.get("package_purchase_id"),
        )
        return Response(
            BookingDetailSerializer(booking, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class BookingDetailView(APIView):
    permission_classes = [IsStudentOrMentor]

    @extend_schema(
        tags=TAG,
        summary="Get one of my bookings",
        responses={200: BookingDetailSerializer, **errors(AUTHED, E404)},
    )
    def get(self, request, pk):
        booking = get_object_or_404(bookings_for(request.user).prefetch_related("events"), pk=pk)
        return Response(BookingDetailSerializer(booking, context={"request": request}).data)


class _BookingActionView(APIView):
    permission_classes = [IsStudentOrMentor]

    def booking(self, request, pk) -> Booking:
        return get_object_or_404(bookings_for(request.user), pk=pk)

    def respond(self, request, booking):
        return Response(BookingDetailSerializer(booking, context={"request": request}).data)


class BookingCancelView(_BookingActionView):
    @extend_schema(
        tags=TAG,
        summary="Cancel a booking",
        description=(
            "Students: free before the mentor accepts; once confirmed, a full refund up to "
            "`FREE_CANCELLATION_HOURS` (24h) before the start, no refund after. Mentors: confirmed bookings "
            "only, reason required, always a full refund. The outcome is recorded in `refund_outcome`; any "
            "refund is executed by the payment provider, never marked as done here."
        ),
        request=ReasonSerializer,
        responses={200: BookingDetailSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.cancel_booking(
            self.booking(request, pk), actor=request.user, reason=serializer.validated_data.get("reason", "")
        )
        return self.respond(request, booking)


class BookingAcceptView(_BookingActionView):
    permission_classes = [IsMentor]

    @extend_schema(
        tags=TAG,
        summary="Accept a booking request (mentor)",
        request=AcceptBookingSerializer,
        responses={200: BookingDetailSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        serializer = AcceptBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.accept_booking(
            self.booking(request, pk),
            actor=request.user,
            meeting_place=serializer.validated_data.get("meeting_place", ""),
            meeting_url=serializer.validated_data.get("meeting_url", ""),
        )
        return self.respond(request, booking)


class BookingMeetingLinkView(_BookingActionView):
    permission_classes = [IsMentor]

    @extend_schema(
        tags=TAG,
        summary="Set the call link for an online session (mentor)",
        description="Use any video tool you and the student agree on. Shown to the student once confirmed.",
        request=MeetingLinkSerializer,
        responses={200: BookingDetailSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        serializer = MeetingLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.set_meeting_link(
            self.booking(request, pk),
            actor=request.user,
            meeting_url=serializer.validated_data["meeting_url"],
        )
        return self.respond(request, booking)


class BookingMeetingPlaceView(_BookingActionView):
    permission_classes = [IsMentor]

    @extend_schema(
        tags=TAG,
        summary="Set where to meet for an in-person session (mentor)",
        description="Shown to the student once the session is confirmed. Never included in emails.",
        request=MeetingPlaceSerializer,
        responses={200: BookingDetailSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        serializer = MeetingPlaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.set_meeting_place(
            self.booking(request, pk),
            actor=request.user,
            meeting_place=serializer.validated_data["meeting_place"],
        )
        return self.respond(request, booking)


class BookingDeclineView(_BookingActionView):
    permission_classes = [IsMentor]

    @extend_schema(
        tags=TAG,
        summary="Decline a booking request (mentor)",
        request=RequiredReasonSerializer,
        responses={200: BookingDetailSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        serializer = RequiredReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.decline_booking(
            self.booking(request, pk), actor=request.user, reason=serializer.validated_data["reason"]
        )
        return self.respond(request, booking)


class BookingCompleteView(_BookingActionView):
    permission_classes = [IsMentor]

    @extend_schema(
        tags=TAG,
        summary="Mark a session as completed (mentor)",
        request=None,
        responses={200: BookingDetailSerializer, **errors(AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        return self.respond(request, services.complete_booking(self.booking(request, pk), actor=request.user))


class BookingCheckoutView(_BookingActionView):
    permission_classes = [IsStudent]

    @extend_schema(
        tags=TAG,
        summary="Start (or resume) checkout for a held booking",
        description="Creates the provider checkout with the server-side amount and returns its URL. "
        "Repeated calls return the same open checkout. Payment success is recorded only from the "
        "provider's verified webhook; the browser's return from checkout changes nothing. "
        "503 `payments_unavailable` while no provider is configured.",
        request=None,
        responses={200: CheckoutSerializer, **errors(AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        from apps.payments.services import start_checkout

        payment = start_checkout(self.booking(request, pk), student=request.user)
        return Response(
            CheckoutSerializer(
                {
                    "payment_id": payment.pk,
                    "checkout_url": payment.checkout_url,
                    "expires_at": payment.checkout_expires_at,
                    "livemode": payment.livemode,
                }
            ).data
        )


@extend_schema(
    tags=["Admin"],
    summary="List all bookings",
    parameters=[
        OpenApiParameter("status", str, enum=BookingStatus.values),
        OpenApiParameter("mentor", str, description="Mentor profile UUID"),
        OpenApiParameter("student", str, description="Student user UUID"),
    ],
    responses={200: BookingSerializer(many=True), **AUTHED},
)
class AdminBookingListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = BookingSerializer
    pagination_class = LargePagination

    def get_queryset(self):
        qs = Booking.objects.select_related(
            "mentor__user", "student", "package_purchase", "seminar"
        ).order_by("-start_at")
        params = self.request.query_params
        if (value := params.get("status")) in BookingStatus.values:
            qs = qs.filter(status=value)
        for param, field in (("mentor", "mentor_id"), ("student", "student_id")):
            if value := params.get(param):
                try:
                    qs = qs.filter(**{field: uuid.UUID(value)})
                except ValueError:
                    return qs.none()
        return qs


@extend_schema(
    tags=["Admin"],
    summary="Get any booking",
    responses={200: BookingDetailSerializer, **errors(AUTHED, E404)},
)
class AdminBookingDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = BookingDetailSerializer
    queryset = Booking.objects.select_related(
        "mentor__user", "student", "package_purchase", "seminar"
    ).prefetch_related("events")


class AdminBookingMeetingPlaceView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Admin"],
        summary="Reveal the exact meeting place of an in-person booking",
        description="For safety and incident handling. Works in any status. A reason is required and every "
        "request is recorded in the audit log (the place itself is not logged).",
        request=RequiredReasonSerializer,
        responses={200: MeetingPlaceRevealSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        booking = get_object_or_404(Booking.objects.select_related("seminar"), pk=pk)
        serializer = RequiredReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.reveal_meeting_place(
            booking, actor=request.user, reason=serializer.validated_data["reason"], request=request
        )
        return Response(MeetingPlaceRevealSerializer(result).data)


class AdminCancelSerializer(RequiredReasonSerializer):
    refund = serializers.BooleanField(
        default=True, help_text="Refund a captured payment in full. Ignored for unpaid bookings."
    )


class AdminBookingCancelView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Admin"],
        summary="Cancel any active booking",
        description="Releases any uncaptured authorisation; refunds a captured payment in full when "
        "`refund` is true. Both participants are emailed. Audit-logged.",
        request=AdminCancelSerializer,
        responses={200: BookingDetailSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk)
        serializer = AdminCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.admin_cancel_booking(
            booking,
            actor=request.user,
            reason=serializer.validated_data["reason"],
            refund=serializer.validated_data["refund"],
        )
        return Response(BookingDetailSerializer(booking, context={"request": request}).data)
