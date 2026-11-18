from django.contrib import admin

from .models import Seminar


@admin.register(Seminar)
class SeminarAdmin(admin.ModelAdmin):
    """Read-only: seminars change through the mentor and admin workflows (which notify students)."""

    list_display = ["title", "mentor", "start_at", "capacity", "price_cents", "status"]
    list_filter = ["status", "format"]
    search_fields = ["title", "mentor__slug"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
