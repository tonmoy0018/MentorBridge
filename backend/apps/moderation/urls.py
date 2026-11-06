from django.urls import path

from . import views

urlpatterns = [path("", views.ReportCreateView.as_view(), name="reports")]

admin_urlpatterns = [
    path("reports/", views.AdminReportListView.as_view(), name="admin-reports"),
    path("reports/<uuid:pk>/resolve/", views.AdminReportResolveView.as_view(), name="admin-report-resolve"),
]
