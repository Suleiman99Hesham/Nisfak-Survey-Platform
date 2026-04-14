from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class ReportExport(UUIDModel, TimeStampedModel):
    class ExportFormat(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "XLSX"
        PDF = "pdf", "PDF"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    survey = models.ForeignKey(
        "surveys.Survey", on_delete=models.CASCADE, related_name="exports"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    export_format = models.CharField(max_length=10, choices=ExportFormat.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    file_path = models.FileField(upload_to="exports/%Y/%m/", null=True, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Export {self.id} - {self.survey.title} ({self.export_format})"


class SurveyInvitation(UUIDModel, TimeStampedModel):
    """Invitation to complete a survey, sent in bulk via email."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        OPENED = "opened", "Opened"

    survey = models.ForeignKey(
        "surveys.Survey", on_delete=models.CASCADE, related_name="invitations"
    )
    batch_id = models.UUIDField(db_index=True)
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["survey", "status"]),
            models.Index(fields=["batch_id"]),
        ]

    def __str__(self):
        return f"Invitation {self.email} -> {self.survey.title}"
