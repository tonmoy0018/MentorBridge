from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_display_name = serializers.CharField(source="student.short_name", read_only=True)
    service_title = serializers.CharField(source="booking.service_title", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "rating", "comment", "created_at", "reviewer_display_name", "service_title"]
        read_only_fields = fields


class CreateReviewSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class AdminReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="student.full_name", read_only=True)
    mentor_name = serializers.CharField(source="mentor.user.full_name", read_only=True)
    mentor_slug = serializers.CharField(source="mentor.slug", read_only=True)
    booking_id = serializers.UUIDField(source="booking.id", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "rating",
            "comment",
            "status",
            "hidden_reason",
            "reviewer_name",
            "mentor_name",
            "mentor_slug",
            "booking_id",
            "created_at",
        ]
        read_only_fields = fields
