from django.urls import path

from apps.reviews.views import MentorReviewListView

from . import views

public_urlpatterns = [
    path("", views.MentorListView.as_view(), name="mentors"),
    path("<str:identifier>/", views.MentorDetailView.as_view(), name="mentor"),
    path(
        "<str:identifier>/availability/", views.MentorAvailabilityView.as_view(), name="mentor-availability"
    ),
    path("<str:identifier>/reviews/", MentorReviewListView.as_view(), name="mentor-reviews"),
]

me_urlpatterns = [
    path("profile/", views.MyMentorProfileView.as_view(), name="my-mentor-profile"),
    path("profile/avatar/", views.MyMentorAvatarView.as_view(), name="my-mentor-avatar"),
    path("experiences/", views.MyExperienceListView.as_view(), name="my-experiences"),
    path("experiences/<uuid:pk>/", views.MyExperienceDetailView.as_view(), name="my-experience"),
    path("services/", views.MyServiceListView.as_view(), name="my-services"),
    path("services/<uuid:pk>/", views.MyServiceDetailView.as_view(), name="my-service"),
    path("availability/rules/", views.MyAvailabilityRulesView.as_view(), name="my-availability-rules"),
    path(
        "availability/exceptions/",
        views.MyAvailabilityExceptionListView.as_view(),
        name="my-availability-exceptions",
    ),
    path(
        "availability/exceptions/<uuid:pk>/",
        views.MyAvailabilityExceptionDetailView.as_view(),
        name="my-availability-exception",
    ),
    path("verification/", views.MyVerificationView.as_view(), name="my-verification"),
]

admin_urlpatterns = [
    path("verification-requests/", views.AdminVerificationListView.as_view(), name="admin-verifications"),
    path(
        "verification-requests/<uuid:pk>/approve/",
        views.AdminVerificationApproveView.as_view(),
        name="admin-verification-approve",
    ),
    path(
        "verification-requests/<uuid:pk>/reject/",
        views.AdminVerificationRejectView.as_view(),
        name="admin-verification-reject",
    ),
]
