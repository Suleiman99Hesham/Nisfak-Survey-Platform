from django.contrib import admin

from apps.analytics.models import ReportExport, SurveyInvitation


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ["id", "survey", "requested_by", "export_format", "status", "created_at", "completed_at"]
    list_filter = ["status", "export_format"]
    readonly_fields = ["file_path", "error_message"]


@admin.register(SurveyInvitation)
class SurveyInvitationAdmin(admin.ModelAdmin):
    list_display = ["id", "survey", "email", "status", "batch_id", "sent_at", "created_at"]
    list_filter = ["status"]
    search_fields = ["email", "batch_id"]
    readonly_fields = ["token", "error_message"]
