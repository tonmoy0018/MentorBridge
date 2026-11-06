from django.contrib import admin

from .models import Booking, BookingEvent


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    can_delete = False
    readonly_fields = ["from_status", "to_status", "actor", "note", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """Read-only: booking state changes must go through the audited service layer."""

    list_display = ["service_title", "mentor", "student", "start_at", "status", "price_cents"]
    list_filter = ["status"]
    search_fields = ["service_title", "student__email", "mentor__slug"]
    inlines = [BookingEventInline]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Booking._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
