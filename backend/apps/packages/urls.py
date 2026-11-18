from django.urls import path

from . import views

me_mentor_urlpatterns = [
    path("packages/", views.MyPackageListView.as_view(), name="my-packages"),
    path("packages/<uuid:pk>/", views.MyPackageDetailView.as_view(), name="my-package"),
]

me_student_urlpatterns = [
    path("packages/", views.MyPackagePurchaseListView.as_view(), name="my-package-purchases"),
    path("packages/<uuid:pk>/", views.MyPackagePurchaseDetailView.as_view(), name="my-package-purchase"),
]

public_urlpatterns = [
    path("<uuid:pk>/purchase/", views.PackagePurchaseCreateView.as_view(), name="package-purchase"),
]
