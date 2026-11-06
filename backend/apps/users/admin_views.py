from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdminRole
from apps.common.schema import AUTHED, E400, E404, errors
from apps.common.serializers import RequiredReasonSerializer

from . import services
from .models import Role, User
from .serializers import AdminUserSerializer

TAG = ["Admin"]


@extend_schema(
    tags=TAG,
    summary="List users",
    parameters=[
        OpenApiParameter("q", str, description="Search name or email"),
        OpenApiParameter("role", str, enum=Role.values),
        OpenApiParameter("is_active", bool),
    ],
    responses={200: AdminUserSerializer(many=True), **AUTHED},
)
class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        qs = User.objects.order_by("-created_at")
        params = self.request.query_params
        if q := params.get("q", "").strip()[:100]:
            qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        if (role := params.get("role")) in Role.values:
            qs = qs.filter(role=role)
        if (active := params.get("is_active")) in ("true", "false"):
            qs = qs.filter(is_active=active == "true")
        return qs


@extend_schema(tags=TAG, summary="Get a user", responses={200: AdminUserSerializer, **errors(AUTHED, E404)})
class AdminUserDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminUserSerializer
    queryset = User.objects.all()


class _UserStatusView(APIView):
    permission_classes = [IsAdminRole]
    activate = False

    def _target(self, request, pk) -> User:
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            raise PermissionDenied("You can't change your own account status.")
        if user.role == Role.ADMIN:
            raise PermissionDenied("Administrator accounts are managed by a superuser in Django admin.")
        return user


class AdminUserSuspendView(_UserStatusView):
    @extend_schema(
        tags=TAG,
        summary="Suspend a user",
        description="The user can no longer log in and their existing sessions stop working. "
        "Suspended mentors disappear from search. Recorded in the audit log.",
        request=RequiredReasonSerializer,
        responses={200: AdminUserSerializer, **errors(E400, AUTHED, E404)},
    )
    def post(self, request, pk):
        user = self._target(request, pk)
        serializer = RequiredReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_active(
            user=user,
            active=False,
            actor=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(AdminUserSerializer(user).data)


class AdminUserReactivateView(_UserStatusView):
    @extend_schema(
        tags=TAG,
        summary="Reactivate a user",
        request=None,
        responses={200: AdminUserSerializer, **errors(AUTHED, E404)},
    )
    def post(self, request, pk):
        user = self._target(request, pk)
        services.set_active(user=user, active=True, actor=request.user, request=request)
        return Response(AdminUserSerializer(user).data)
