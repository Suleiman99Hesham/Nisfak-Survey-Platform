from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id", "timestamp", "actor", "actor_username", "organization",
            "action", "entity_type", "entity_id",
            "changes", "ip_address", "user_agent", "metadata",
        ]
