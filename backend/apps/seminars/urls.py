from django.urls import path

from . import views

me_mentor_urlpatterns = [
    path("seminars/", views.MySeminarListView.as_view(), name="my-seminars"),
    path("seminars/<uuid:pk>/", views.MySeminarDetailView.as_view(), name="my-seminar"),
    path("seminars/<uuid:pk>/cancel/", views.MySeminarCancelView.as_view(), name="my-seminar-cancel"),
    path("seminars/<uuid:pk>/complete/", views.MySeminarCompleteView.as_view(), name="my-seminar-complete"),
]

public_urlpatterns = [
    path("<uuid:pk>/register/", views.SeminarRegisterView.as_view(), name="seminar-register"),
]

admin_urlpatterns = [
    path("seminars/", views.AdminSeminarListView.as_view(), name="admin-seminars"),
    path("seminars/<uuid:pk>/cancel/", views.AdminSeminarCancelView.as_view(), name="admin-seminar-cancel"),
    path(
        "seminars/<uuid:pk>/meeting-place/",
        views.AdminSeminarMeetingPlaceView.as_view(),
        name="admin-seminar-meeting-place",
    ),
]
