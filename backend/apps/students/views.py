from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardPagination
from apps.common.permissions import IsStudent
from apps.common.schema import AUTHED, E404, errors
from apps.mentors import selectors
from apps.mentors.serializers import MentorSummarySerializer

from .models import CareerGoal, SavedMentor, StudentProfile
from .serializers import CareerGoalSerializer, StudentProfileSerializer

TAG = ["Student self-service"]


@extend_schema(tags=TAG)
class MyStudentProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsStudent]
    serializer_class = StudentProfileSerializer
    http_method_names = ["get", "patch"]

    def get_object(self):
        profile, _ = StudentProfile.objects.get_or_create(user=self.request.user)
        return profile


class SavedMentorListView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        tags=TAG,
        summary="List saved mentors",
        description="Only mentors that are still publicly listed are returned.",
        responses={200: MentorSummarySerializer(many=True), **AUTHED},
    )
    def get(self, request):
        mentors = (
            selectors.public_mentors()
            .filter(saved_by__student=request.user)
            .order_by("-saved_by__created_at")
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(mentors, request, view=self)
        context = {
            "request": request,
            "next_available": selectors.next_available_map(list(page), timezone.now()),
        }
        return paginator.get_paginated_response(
            MentorSummarySerializer(page, many=True, context=context).data
        )


class SavedMentorDetailView(APIView):
    """`mentor_id` is the mentor's slug or UUID. Both operations are idempotent."""

    permission_classes = [IsStudent]

    @extend_schema(
        tags=TAG, summary="Save a mentor", request=None, responses={204: None, **errors(AUTHED, E404)}
    )
    def put(self, request, mentor_id):
        mentor = selectors.get_public_mentor(mentor_id)
        SavedMentor.objects.get_or_create(student=request.user, mentor=mentor)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(tags=TAG, summary="Remove a saved mentor", responses={204: None, **errors(AUTHED, E404)})
    def delete(self, request, mentor_id):
        from apps.mentors.models import MentorProfile

        # Allow removing bookmarks of mentors who are no longer listed.
        mentor = selectors.get_public_mentor(mentor_id, MentorProfile.objects.all())
        SavedMentor.objects.filter(student=request.user, mentor=mentor).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=TAG)
class CareerGoalListView(generics.ListCreateAPIView):
    permission_classes = [IsStudent]
    serializer_class = CareerGoalSerializer

    def get_queryset(self):
        return CareerGoal.objects.filter(student=self.request.user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


@extend_schema(tags=TAG)
class CareerGoalDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsStudent]
    serializer_class = CareerGoalSerializer
    http_method_names = ["get", "patch", "delete"]

    def get_queryset(self):
        return CareerGoal.objects.filter(student=self.request.user)
