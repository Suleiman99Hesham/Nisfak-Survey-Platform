from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "actor", "action", "entity_type", "entity_id", "ip_address"]
    list_filter = ["action", "entity_type"]
    search_fields = ["entity_id", "actor__username"]
    readonly_fields = [
        "timestamp", "actor", "organization", "action",
        "entity_type", "entity_id", "changes", "ip_address",
        "user_agent", "metadata",
    ]
