from django.urls import path

from . import views

me_urlpatterns = [
    path("earnings/summary/", views.EarningsSummaryView.as_view(), name="my-earnings-summary"),
    path("earnings/ledger/", views.LedgerView.as_view(), name="my-earnings-ledger"),
    path("payouts/", views.PayoutListView.as_view(), name="my-payouts"),
]

webhook_urlpatterns = [
    path("webhooks/<slug:provider>/", views.PaymentWebhookView.as_view(), name="payment-webhook"),
]

admin_urlpatterns = [
    path("payments/", views.AdminPaymentListView.as_view(), name="admin-payments"),
    path("payments/<uuid:pk>/", views.AdminPaymentDetailView.as_view(), name="admin-payment"),
    path("payments/<uuid:pk>/refund/", views.AdminPaymentRefundView.as_view(), name="admin-payment-refund"),
    path("refunds/", views.AdminRefundListView.as_view(), name="admin-refunds"),
]
