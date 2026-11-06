from django.urls import path

from apps.reviews.views import BookingReviewCreateView

from . import views

urlpatterns = [
    path("", views.BookingListCreateView.as_view(), name="bookings"),
    path("<uuid:pk>/", views.BookingDetailView.as_view(), name="booking"),
    path("<uuid:pk>/cancel/", views.BookingCancelView.as_view(), name="booking-cancel"),
    path("<uuid:pk>/accept/", views.BookingAcceptView.as_view(), name="booking-accept"),
    path("<uuid:pk>/decline/", views.BookingDeclineView.as_view(), name="booking-decline"),
    path("<uuid:pk>/complete/", views.BookingCompleteView.as_view(), name="booking-complete"),
    path("<uuid:pk>/checkout/", views.BookingCheckoutView.as_view(), name="booking-checkout"),
    path("<uuid:pk>/review/", BookingReviewCreateView.as_view(), name="booking-review"),
]

admin_urlpatterns = [
    path("bookings/", views.AdminBookingListView.as_view(), name="admin-bookings"),
    path("bookings/<uuid:pk>/", views.AdminBookingDetailView.as_view(), name="admin-booking"),
    path("bookings/<uuid:pk>/cancel/", views.AdminBookingCancelView.as_view(), name="admin-booking-cancel"),
]
