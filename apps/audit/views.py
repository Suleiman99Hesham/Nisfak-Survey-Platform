from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdmin
from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["action", "entity_type", "entity_id", "actor"]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return AuditLog.objects.none()
        return AuditLog.objects.filter(
            organization=membership.organization
        ).select_related("actor")


class AuditLogDetailView(generics.RetrieveAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return AuditLog.objects.none()
        return AuditLog.objects.filter(
            organization=membership.organization
        ).select_related("actor")
