from rest_framework import serializers

from .models import Report, ReportReason, ReportStatus, ReportTargetType


class ReportCreateSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=ReportTargetType.choices)
    target_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=ReportReason.choices)
    details = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "target_type",
            "target_id",
            "target_label",
            "reason",
            "details",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class AdminReportSerializer(ReportSerializer):
    reporter_display_name = serializers.SerializerMethodField()

    class Meta(ReportSerializer.Meta):
        fields = [*ReportSerializer.Meta.fields, "reporter_display_name", "resolution_note", "resolved_at"]
        read_only_fields = fields

    def get_reporter_display_name(self, obj) -> str:
        return obj.reporter.full_name if obj.reporter else "Deleted user"


class ResolveReportSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=[ReportStatus.ACTIONED, ReportStatus.DISMISSED])
    note = serializers.CharField(max_length=2000)
    hide_review = serializers.BooleanField(
        default=False, help_text="Hide the reported review (review reports only)."
    )
