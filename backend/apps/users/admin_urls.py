from django.urls import path

from . import admin_views

urlpatterns = [
    path("users/", admin_views.AdminUserListView.as_view(), name="admin-users"),
    path("users/<uuid:pk>/", admin_views.AdminUserDetailView.as_view(), name="admin-user"),
    path("users/<uuid:pk>/suspend/", admin_views.AdminUserSuspendView.as_view(), name="admin-user-suspend"),
    path(
        "users/<uuid:pk>/reactivate/",
        admin_views.AdminUserReactivateView.as_view(),
        name="admin-user-reactivate",
    ),
]
