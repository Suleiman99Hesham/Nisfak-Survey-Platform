from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="audit_logs",
    )
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    action = models.CharField(max_length=50, db_index=True)
    # e.g. "survey.create", "survey.publish", "response.submit", "export.request"
    entity_type = models.CharField(max_length=50, db_index=True)
    entity_id = models.CharField(max_length=36)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor", "timestamp"]),
            models.Index(fields=["organization", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.timestamp}"
