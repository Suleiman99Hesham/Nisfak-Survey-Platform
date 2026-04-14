from apps.audit.services import log_action


class AuditLogMixin:
    """
    Mixin for DRF views that automatically logs create, update, and delete actions.

    Usage:
        class MyView(AuditLogMixin, generics.CreateAPIView):
            audit_entity_type = "survey"
            ...
    """

    audit_entity_type = None  # Must be set by the view

    def perform_create(self, serializer):
        instance = serializer.save()
        if self.audit_entity_type:
            log_action(
                actor=self.request.user,
                action=f"{self.audit_entity_type}.create",
                entity_type=self.audit_entity_type,
                entity_id=str(instance.pk),
                request=self.request,
            )
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        if self.audit_entity_type:
            log_action(
                actor=self.request.user,
                action=f"{self.audit_entity_type}.update",
                entity_type=self.audit_entity_type,
                entity_id=str(instance.pk),
                request=self.request,
            )
        return instance

    def perform_destroy(self, instance):
        entity_id = str(instance.pk)
        instance.delete()
        if self.audit_entity_type:
            log_action(
                actor=self.request.user,
                action=f"{self.audit_entity_type}.delete",
                entity_type=self.audit_entity_type,
                entity_id=entity_id,
                request=self.request,
            )
