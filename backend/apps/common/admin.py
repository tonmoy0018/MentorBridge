from django.contrib import admin

from .models import AuditLogEntry


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "target_type", "target_id", "actor"]
    list_filter = ["action", "target_type"]
    search_fields = ["target_id", "actor__email"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in AuditLogEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
