from django.utils import timezone
from django_countries.serializer_fields import CountryField
from rest_framework import serializers

from apps.taxonomy.models import Category

from .models import CareerGoal, GoalStatus, StudentProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    interest_ids = serializers.PrimaryKeyRelatedField(
        source="interests", queryset=Category.objects.filter(is_active=True), many=True, required=False
    )
    country = CountryField(allow_blank=True, required=False)

    class Meta:
        model = StudentProfile
        fields = ["id", "headline", "education", "bio", "country", "interest_ids", "updated_at"]
        read_only_fields = ["id", "updated_at"]

    def validate_interest_ids(self, value):
        if len(set(value)) > 10:
            raise serializers.ValidationError("Choose up to 10 career interests.")
        return list(set(value))


class CareerGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareerGoal
        fields = ["id", "title", "description", "status", "target_date", "achieved_at", "created_at"]
        read_only_fields = ["id", "achieved_at", "created_at"]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Give your goal a title.")
        return value.strip()

    def save(self, **kwargs):
        status = self.validated_data.get("status")
        if status == GoalStatus.ACHIEVED and (self.instance is None or self.instance.achieved_at is None):
            kwargs["achieved_at"] = timezone.now()
        elif status and status != GoalStatus.ACHIEVED:
            kwargs["achieved_at"] = None
        return super().save(**kwargs)
