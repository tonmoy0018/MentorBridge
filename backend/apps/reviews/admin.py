from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["mentor", "student", "rating", "status", "created_at"]
    list_filter = ["status", "rating"]
    readonly_fields = ["booking", "student", "mentor", "rating", "comment", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False
