from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.MyStudentProfileView.as_view(), name="my-student-profile"),
    path("saved-mentors/", views.SavedMentorListView.as_view(), name="saved-mentors"),
    path("saved-mentors/<str:mentor_id>/", views.SavedMentorDetailView.as_view(), name="saved-mentor"),
    path("goals/", views.CareerGoalListView.as_view(), name="goals"),
    path("goals/<uuid:pk>/", views.CareerGoalDetailView.as_view(), name="goal"),
]
