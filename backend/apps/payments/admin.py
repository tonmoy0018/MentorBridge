from django.contrib import admin

from .models import Payment, Payout, Refund, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Strictly read-only: payment state may only change via verified provider events."""

    list_display = ["id", "booking", "provider", "status", "refund_status", "amount_cents", "created_at"]
    list_filter = ["status", "refund_status", "provider"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ["mentor", "amount_cents", "currency", "status", "method", "paid_at"]
    list_filter = ["status", "method"]
    readonly_fields = ["created_by", "created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """Read-only: refunds are created through the audited admin API so they reach the provider."""

    list_display = ["payment", "amount_cents", "reason", "status", "created_at"]
    list_filter = ["status", "reason"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Refund._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ["provider", "event_type", "event_id", "outcome", "received_at", "processed_at"]
    list_filter = ["provider", "event_type", "outcome"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in WebhookEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
