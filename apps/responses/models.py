from django.conf import settings
from django.db import models

from apps.common.models import UUIDModel


class SurveySubmission(UUIDModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        ABANDONED = "abandoned", "Abandoned"

    survey = models.ForeignKey(
        "surveys.Survey", on_delete=models.CASCADE, related_name="submissions"
    )
    survey_version = models.ForeignKey(
        "surveys.SurveyVersion", on_delete=models.CASCADE, related_name="submissions"
    )
    respondent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="submissions",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS
    )
    resume_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_saved_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completion_percentage = models.FloatField(default=0.0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["survey", "status"]),
            models.Index(fields=["respondent", "status"]),
            models.Index(fields=["resume_token"]),
            models.Index(fields=["survey", "submitted_at"]),
        ]

    def __str__(self):
        return f"Submission {self.id} - {self.survey.title} ({self.status})"


class Answer(models.Model):
    """
    Stores a single answer for a field in a submission.
    Uses typed columns for analytics query performance.
    Only one value column is populated per answer, based on the field type.
    """
    id = models.BigAutoField(primary_key=True)
    submission = models.ForeignKey(
        SurveySubmission, on_delete=models.CASCADE, related_name="answers"
    )
    field = models.ForeignKey(
        "surveys.SurveyField", on_delete=models.CASCADE, related_name="answers"
    )

    # Typed value columns — only one is populated per answer
    value_text = models.TextField(null=True, blank=True)
    value_number = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True
    )
    value_date = models.DateField(null=True, blank=True)
    value_datetime = models.DateTimeField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True)
    value_json = models.JSONField(null=True, blank=True)
    # value_json used for: checkbox (list), matrix (dict), file metadata

    # Encrypted value for sensitive fields
    value_encrypted = models.BinaryField(null=True, blank=True)

    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("submission", "field")]
        indexes = [
            models.Index(fields=["field", "value_text"]),
            models.Index(fields=["field", "value_number"]),
        ]

    def __str__(self):
        return f"Answer for {self.field_id} in submission {self.submission_id}"
