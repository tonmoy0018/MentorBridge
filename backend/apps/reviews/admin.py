from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["mentor", "student", "rating", "status", "created_at"]
    list_filter = ["status", "rating"]
    readonly_fields = [
        "booking",
        "student",
        "mentor",
        "rating",
        "comment",
        "status",
        "hidden_reason",
        "created_at",
        "updated_at",
    ]

    # Moderate in the admin dashboard (/dashboard/admin/reviews), which recalculates the
    # mentor's rating and writes the audit log. Here reviews are read-only.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
