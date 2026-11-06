from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers

from apps.common.permissions import IsAdminRole
from apps.common.schema import AUTHED

from .models import EmailNotification, NotificationStatus


class AdminNotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.SerializerMethodField()

    class Meta:
        model = EmailNotification
        # Deliberately no email address or rendered content.
        fields = [
            "id",
            "template",
            "status",
            "attempts",
            "last_error",
            "recipient_name",
            "sent_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_recipient_name(self, obj) -> str:
        return obj.recipient.full_name if obj.recipient else "Deleted user"


@extend_schema(
    tags=["Admin"],
    summary="Email notification log",
    parameters=[
        OpenApiParameter("status", str, enum=NotificationStatus.values),
        OpenApiParameter("template", str),
    ],
    responses={200: AdminNotificationSerializer(many=True), **AUTHED},
)
class AdminNotificationListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminNotificationSerializer

    def get_queryset(self):
        qs = EmailNotification.objects.select_related("recipient")
        params = self.request.query_params
        if (value := params.get("status")) in NotificationStatus.values:
            qs = qs.filter(status=value)
        if template := params.get("template"):
            qs = qs.filter(template=template)
        return qs
