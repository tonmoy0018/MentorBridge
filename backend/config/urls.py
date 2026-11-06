from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.bookings.urls import admin_urlpatterns as booking_admin
from apps.common.admin_security import throttle_admin_login
from apps.common.admin_views import AdminAuditLogView, AdminStatsView
from apps.common.views import HealthView, PublicConfigView
from apps.mentors.urls import admin_urlpatterns as mentor_admin
from apps.mentors.urls import me_urlpatterns as mentor_me
from apps.mentors.urls import public_urlpatterns as mentor_public
from apps.moderation.urls import admin_urlpatterns as moderation_admin
from apps.notifications.views import AdminNotificationListView
from apps.payments.urls import admin_urlpatterns as payment_admin
from apps.payments.urls import me_urlpatterns as payment_me
from apps.payments.urls import webhook_urlpatterns
from apps.reviews.views import AdminReviewHideView, AdminReviewListView, AdminReviewPublishView
from apps.taxonomy.urls import category_urlpatterns, taxonomy_urlpatterns
from apps.users.admin_urls import urlpatterns as user_admin

admin_api = [
    path("stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("audit-log/", AdminAuditLogView.as_view(), name="admin-audit-log"),
    path("notifications/", AdminNotificationListView.as_view(), name="admin-notifications"),
    path("reviews/", AdminReviewListView.as_view(), name="admin-reviews"),
    path("reviews/<uuid:pk>/hide/", AdminReviewHideView.as_view(), name="admin-review-hide"),
    path("reviews/<uuid:pk>/publish/", AdminReviewPublishView.as_view(), name="admin-review-publish"),
    *user_admin,
    *mentor_admin,
    *booking_admin,
    *payment_admin,
    *moderation_admin,
]

api_v1 = [
    path("health/", HealthView.as_view(), name="health"),
    path("config/", PublicConfigView.as_view(), name="config"),
    path("auth/", include("apps.users.urls")),
    path("categories/", include(category_urlpatterns)),
    path("taxonomy/", include(taxonomy_urlpatterns)),
    path("mentors/", include(mentor_public)),
    path("me/mentor/", include([*mentor_me, *payment_me])),
    path("me/student/", include("apps.students.urls")),
    path("bookings/", include("apps.bookings.urls")),
    path("reports/", include("apps.moderation.urls")),
    path("payments/", include(webhook_urlpatterns)),
    path("admin/", include(admin_api)),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

# Must be wrapped before `admin.site.urls` is built, which binds the login view.
admin.site.login = throttle_admin_login(admin.site.login)

urlpatterns = [
    path("api/v1/", include(api_v1)),
    path(settings.ADMIN_URL, admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "MentorBridge administration"
