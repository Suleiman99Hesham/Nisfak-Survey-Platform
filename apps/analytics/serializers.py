from rest_framework import serializers

from apps.analytics.models import ReportExport, SurveyInvitation


class ReportExportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportExport
        fields = [
            "id", "survey", "requested_by", "export_format", "status",
            "file_path", "filters", "error_message",
            "created_at", "completed_at",
        ]
        read_only_fields = [
            "id", "survey", "requested_by", "status",
            "file_path", "error_message", "created_at", "completed_at",
        ]


class SurveyInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyInvitation
        fields = [
            "id", "survey", "batch_id", "email", "status",
            "invited_by", "sent_at", "opened_at", "error_message", "created_at",
        ]
        read_only_fields = fields


class InvitationRequestSerializer(serializers.Serializer):
    emails = serializers.ListField(
        child=serializers.EmailField(),
        allow_empty=False,
        min_length=1,
        max_length=10000,
    )
