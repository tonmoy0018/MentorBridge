from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsStudent
from apps.common.schema import AUTHED, E400, E404, E409, E429, errors
from apps.common.throttling import IPScopedThrottle
from apps.mentors.views import ME, MentorSelfMixin, _validation

from . import services
from .models import MentorPackage, PackagePurchase, PurchaseStatus
from .serializers import (
    PackagePurchaseSerializer,
    PackageSerializer,
    PackageWriteSerializer,
    PurchaseRequestSerializer,
    PurchaseResponseSerializer,
)

STUDENT = ["Student self-service"]


class MyPackageListView(MentorSelfMixin, generics.ListAPIView):
    serializer_class = PackageSerializer
    pagination_class = None

    def get_queryset(self):
        return MentorPackage.objects.filter(mentor=self.get_mentor()).select_related("service")

    @extend_schema(tags=ME, summary="List my session packages (including hidden ones)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=ME,
        summary="Create a session package",
        description="N sessions of one of your services at a package price, used within `validity_days`.",
        request=PackageWriteSerializer,
        responses={201: PackageSerializer, **errors(E400, AUTHED)},
    )
    def post(self, request):
        serializer = PackageWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            package = services.create_package(self.get_mentor(), serializer.validated_data)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(PackageSerializer(package).data, status=status.HTTP_201_CREATED)


class MyPackageDetailView(MentorSelfMixin, APIView):
    def _get(self, pk) -> MentorPackage:
        return get_object_or_404(
            MentorPackage.objects.select_related("service"), pk=pk, mentor=self.get_mentor()
        )

    @extend_schema(
        tags=ME,
        summary="Update a session package",
        description="Changes apply to new purchases only.",
        request=PackageWriteSerializer,
        responses={200: PackageSerializer, **errors(E400, AUTHED, E404)},
    )
    def patch(self, request, pk):
        package = self._get(pk)
        serializer = PackageWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_package(package, serializer.validated_data)
        except DjangoValidationError as exc:
            raise _validation(exc) from exc
        return Response(PackageSerializer(package).data)

    @extend_schema(
        tags=ME,
        summary="Delete a package nobody has bought",
        responses={204: None, **errors(AUTHED, E404, E409)},
    )
    def delete(self, request, pk):
        services.delete_package(self._get(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class PackagePurchaseCreateView(APIView):
    permission_classes = [IsStudent]
    throttle_scope = "booking_create"

    def get_throttles(self):
        return [IPScopedThrottle()]

    @extend_schema(
        tags=["Packages"],
        summary="Buy a multi-session option",
        description=(
            "Starts (or resumes) checkout for the bundle in the chosen format. The bundle stays "
            "`pending_payment` and can't be used until the payment provider confirms payment; a browser "
            "redirect back from checkout changes nothing."
        ),
        request=PurchaseRequestSerializer,
        responses={201: PurchaseResponseSerializer, **errors(E400, AUTHED, E404, E409, E429)},
    )
    def post(self, request, pk):
        serializer = PurchaseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase, checkout_url = services.purchase_package(
            student=request.user, package_id=pk, session_format=serializer.validated_data.get("format")
        )
        purchase = PackagePurchase.objects.with_usage().select_related("mentor__user").get(pk=purchase.pk)
        return Response(
            {
                "purchase": PackagePurchaseSerializer(purchase, context={"request": request}).data,
                "checkout_url": checkout_url,
            },
            status=status.HTTP_201_CREATED,
        )


class MyPackagePurchaseDetailView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        tags=STUDENT,
        summary="Get one of my session packages",
        description="Poll this after checkout: `status` becomes `active` once payment is confirmed.",
        responses={200: PackagePurchaseSerializer, **errors(AUTHED, E404)},
    )
    def get(self, request, pk):
        qs = PackagePurchase.objects.filter(student=request.user).select_related("mentor__user").with_usage()
        return Response(
            PackagePurchaseSerializer(get_object_or_404(qs, pk=pk), context={"request": request}).data
        )


class MyPackagePurchaseListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = PackagePurchaseSerializer
    pagination_class = None

    def get_queryset(self):
        # Abandoned checkouts aren't the student's packages.
        qs = (
            PackagePurchase.objects.filter(student=self.request.user)
            .exclude(status=PurchaseStatus.CANCELLED)
            .select_related("mentor__user")
            .with_usage()
        )
        if mentor := self.request.query_params.get("mentor"):
            qs = qs.filter(mentor_id=mentor) if _is_uuid(mentor) else qs.none()
        return qs

    @extend_schema(
        tags=STUDENT,
        summary="List my session packages",
        parameters=[OpenApiParameter("mentor", str, description="Only packages with this mentor (id).")],
        responses={200: PackagePurchaseSerializer(many=True), **AUTHED},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
