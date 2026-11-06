from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminRole, IsStudentOrMentor
from apps.common.schema import AUTHED, E400, E404, E409, E429, errors
from apps.common.throttling import IPScopedThrottle

from . import services
from .models import UNRESOLVED, Report, ReportStatus
from .serializers import (
    AdminReportSerializer,
    ReportCreateSerializer,
    ReportSerializer,
    ResolveReportSerializer,
)


class ReportCreateView(APIView):
    permission_classes = [IsStudentOrMentor]
    throttle_classes = [IPScopedThrottle]
    throttle_scope = "report_create"

    @extend_schema(
        tags=["Reports"],
        summary="Report content",
        description="Report a review, a mentor profile, a booking you took part in, or a user you've had a "
        "booking with. One open report per item per reporter.",
        request=ReportCreateSerializer,
        responses={201: ReportSerializer, **errors(E400, AUTHED, E404, E409, E429)},
    )
    def post(self, request):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.create_report(reporter=request.user, **serializer.validated_data)
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Admin"],
    summary="List reports",
    parameters=[
        OpenApiParameter(
            "status",
            str,
            description="`open` (open + in review, default), `resolved` (actioned + dismissed), "
            "or an exact status.",
        )
    ],
    responses={200: AdminReportSerializer(many=True), **AUTHED},
)
class AdminReportListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminReportSerializer

    def get_queryset(self):
        value = self.request.query_params.get("status", "open")
        qs = Report.objects.select_related("reporter")
        if value == "resolved":
            return qs.filter(status__in=[ReportStatus.ACTIONED, ReportStatus.DISMISSED]).order_by(
                "-resolved_at"
            )
        if value in ReportStatus.values:
            return qs.filter(status=value)
        return qs.filter(status__in=UNRESOLVED).order_by("created_at")


class AdminReportResolveView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        tags=["Admin"],
        summary="Resolve a report",
        request=ResolveReportSerializer,
        responses={200: AdminReportSerializer, **errors(E400, AUTHED, E404, E409)},
    )
    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        serializer = ResolveReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = services.resolve_report(
            report, actor=request.user, request=request, **serializer.validated_data
        )
        return Response(AdminReportSerializer(report).data)
