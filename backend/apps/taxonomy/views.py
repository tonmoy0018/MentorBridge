from django.db.models import Count, Q
from django_countries import countries
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.schema import E404

from .models import Category, Language, Profession, Skill
from .serializers import (
    CategorySerializer,
    CountrySerializer,
    LanguageSerializer,
    ProfessionSerializer,
    SkillSerializer,
)

TAG = ["Categories & taxonomy"]
WITH_COUNTS = OpenApiParameter(
    "with_counts", bool, description="Include `mentor_count` (approved, active mentors) per category."
)


def _categories():
    qs = Category.objects.filter(is_active=True)
    return qs


def _with_counts(qs):
    from apps.mentors.models import VerificationStatus

    return qs.annotate(
        mentor_count=Count(
            "mentors",
            filter=Q(mentors__verification_status=VerificationStatus.APPROVED, mentors__user__is_active=True),
            distinct=True,
        )
    )


@extend_schema(tags=TAG, summary="List categories", parameters=[WITH_COUNTS])
class CategoryListView(generics.ListAPIView):
    """Active categories (industries). Not paginated: it's a short, fixed list."""

    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        qs = _categories()
        return _with_counts(qs) if self.request.query_params.get("with_counts") == "true" else qs


@extend_schema(tags=TAG, summary="Get a category", responses={200: CategorySerializer, **E404})
class CategoryDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        return _with_counts(_categories())


@extend_schema(
    tags=TAG,
    summary="List professions",
    parameters=[OpenApiParameter("industry", str, description="Category slug")],
)
class ProfessionListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProfessionSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Profession.objects.select_related("category")
        if industry := self.request.query_params.get("industry"):
            qs = qs.filter(category__slug=industry)
        return qs


@extend_schema(tags=TAG, summary="List skills", parameters=[OpenApiParameter("q", str)])
class SkillListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = SkillSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Skill.objects.all()
        if q := self.request.query_params.get("q", "").strip()[:80]:
            qs = qs.filter(name__icontains=q)
        return qs


@extend_schema(tags=TAG, summary="List languages")
class LanguageListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LanguageSerializer
    pagination_class = None
    queryset = Language.objects.all()


class CountryListView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=TAG, summary="List countries (ISO 3166-1)", responses={200: CountrySerializer(many=True)}
    )
    def get(self, request):
        return Response([{"code": code, "name": name} for code, name in countries])
