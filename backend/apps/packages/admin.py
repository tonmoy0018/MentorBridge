from django.contrib import admin

from .models import MentorPackage, PackagePurchase


@admin.register(MentorPackage)
class MentorPackageAdmin(admin.ModelAdmin):
    list_display = ["__str__", "mentor", "session_count", "discount_percent", "validity_days", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["service__title", "mentor__slug"]
    raw_id_fields = ["mentor", "service"]


@admin.register(PackagePurchase)
class PackagePurchaseAdmin(admin.ModelAdmin):
    """Read-only: purchases change only through the package and booking workflows."""

    list_display = ["title", "student", "mentor", "status", "session_count", "expires_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "mentor__slug"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
