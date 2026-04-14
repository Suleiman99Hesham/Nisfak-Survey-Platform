from django.contrib import admin

from apps.responses.models import Answer, SurveySubmission


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ["field", "value_text", "value_number", "value_date", "value_boolean", "value_json", "is_valid"]


@admin.register(SurveySubmission)
class SurveySubmissionAdmin(admin.ModelAdmin):
    list_display = ["id", "survey", "respondent", "status", "completion_percentage", "started_at", "submitted_at"]
    list_filter = ["status", "survey"]
    search_fields = ["id", "resume_token"]
    readonly_fields = ["resume_token"]
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["id", "submission", "field", "value_text", "value_number", "is_valid"]
    list_filter = ["is_valid"]
