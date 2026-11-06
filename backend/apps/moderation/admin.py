from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["target_label", "reason", "status", "reporter", "created_at"]
    list_filter = ["status", "reason", "target_type"]
    readonly_fields = [f.name for f in Report._meta.fields]
