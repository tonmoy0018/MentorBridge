from django.contrib import admin

from .models import (
    AvailabilityException,
    AvailabilityRule,
    MentorExperience,
    MentorProfile,
    MentorService,
    MentorSkill,
    VerificationRequest,
)


class ServiceInline(admin.TabularInline):
    model = MentorService
    extra = 0


class SkillInline(admin.TabularInline):
    model = MentorSkill
    extra = 0


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = ["slug", "user", "verification_status", "rating_avg", "rating_count", "created_at"]
    list_filter = ["verification_status", "is_accepting_bookings"]
    search_fields = ["slug", "user__email", "user__first_name", "user__last_name"]
    # Verification goes through the audited admin API, not direct edits.
    readonly_fields = [
        "verification_status",
        "verified_at",
        "rating_avg",
        "rating_count",
        "created_at",
        "updated_at",
    ]
    inlines = [SkillInline, ServiceInline]


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ["mentor", "status", "submitted_at", "reviewed_by", "reviewed_at"]
    list_filter = ["status"]
    readonly_fields = [f.name for f in VerificationRequest._meta.fields]

    def has_add_permission(self, request):
        return False


admin.site.register(MentorExperience)
admin.site.register(AvailabilityRule)
admin.site.register(AvailabilityException)
