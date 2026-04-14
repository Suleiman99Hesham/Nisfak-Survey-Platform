import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class Organization(UUIDModel, TimeStampedModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        db_table = "auth_user"

    def __str__(self):
        return self.email or self.username


class Membership(UUIDModel, TimeStampedModel):
    """Maps a user to an organization with a specific role."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        DATA_VIEWER = "data_viewer", "Data Viewer"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DATA_VIEWER)

    class Meta:
        unique_together = [("user", "organization")]
        indexes = [
            models.Index(fields=["user", "organization"]),
            models.Index(fields=["organization", "role"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.organization} ({self.role})"
