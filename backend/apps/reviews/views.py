from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.common.pagination import SmallPagination
from apps.common.permissions import IsStudent
from apps.common.schema import AUTHED, E400, E404, E409, E429, errors
from apps.common.throttling import IPScopedThrottle
from apps.mentors.selectors import get_public_mentor

from . import services
from .models import Review, ReviewStatus
from .serializers import CreateReviewSerializer, ReviewSerializer


@extend_schema(
    tags=["Reviews"],
    summary="List a mentor's reviews",
    description="Published reviews only. Every review comes from a completed booking.",
    responses={200: ReviewSerializer(many=True), **E404},
)
class MentorReviewListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ReviewSerializer
    pagination_class = SmallPagination

    def get_queryset(self):
        mentor = get_public_mentor(self.kwargs["identifier"])
        return Review.objects.filter(mentor=mentor, status=ReviewStatus.PUBLISHED).select_related(
            "student", "booking"
        )


class BookingReviewCreateView(APIView):
    permission_classes = [IsStudent]
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "review_create"

    @extend_schema(
        tags=["Reviews"],
        summary="Review a completed session",
        description="Only the booking's student, only once, only after the booking is `completed`. "
        "Ineligible requests return 409 `not_eligible` or `already_exists`.",
        request=CreateReviewSerializer,
        responses={201: ReviewSerializer, **errors(E400, AUTHED, E404, E409, E429)},
    )
    def post(self, request, pk):
        # Scoped to the caller's own bookings: someone else's booking is a 404.
        booking = get_object_or_404(Booking, pk=pk, student=request.user)
        serializer = CreateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = services.create_review(booking=booking, student=request.user, **serializer.validated_data)
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


# --- admin moderation ---------------------------------------------------------------------------

from apps.common.models import record_audit  # noqa: E402
from apps.common.permissions import IsAdminRole  # noqa: E402
from apps.common.serializers import ReasonSerializer  # noqa: E402

from .serializers import AdminReviewSerializer  # noqa: E402


@extend_schema(
    tags=["Admin"],
    summary="List reviews for moderation",
    parameters=[OpenApiParameter("status", str, enum=ReviewStatus.values), OpenApiParameter("mentor", str)],
    responses={200: AdminReviewSerializer(many=True), **AUTHED},
)
class AdminReviewListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminReviewSerializer

    def get_queryset(self):
        qs = Review.objects.select_related("student", "mentor__user", "booking")
        params = self.request.query_params
        if (value := params.get("status")) in ReviewStatus.values:
            qs = qs.filter(status=value)
        if mentor := params.get("mentor"):
            qs = qs.filter(mentor__slug=mentor)
        return qs


class _AdminReviewAction(APIView):
    permission_classes = [IsAdminRole]
    hide = True

    @extend_schema(
        tags=["Admin"],
        request=ReasonSerializer,
        responses={200: AdminReviewSerializer, **errors(E400, AUTHED, E404)},
    )
    def post(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        if self.hide and not reason:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"reason": ["Record why the review is hidden."]})
        review = services.set_review_visibility(review, hidden=self.hide, reason=reason)
        record_audit(
            request.user, "review.hidden" if self.hide else "review.published", review, {"reason": reason}
        )
        return Response(AdminReviewSerializer(review).data)


@extend_schema(summary="Hide a review (recalculates the mentor's rating)")
class AdminReviewHideView(_AdminReviewAction):
    hide = True


@extend_schema(summary="Publish a hidden review again")
class AdminReviewPublishView(_AdminReviewAction):
    hide = False
