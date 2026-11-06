from django.contrib import admin

from .models import EmailNotification


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ["template", "recipient", "status", "attempts", "sent_at", "created_at"]
    list_filter = ["template", "status"]
    # `context` can hold a not-yet-sent verification or reset link, so it's never shown.
    exclude = ["context"]
    readonly_fields = [f.name for f in EmailNotification._meta.fields if f.name != "context"]

    def has_add_permission(self, request):
        return False
