from rest_framework import serializers

from apps.responses.models import Answer, SurveySubmission
from apps.responses.services.encryption import get_encryption


class AnswerSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = ["id", "field", "value", "is_valid", "created_at", "updated_at"]
        read_only_fields = ["id", "is_valid", "created_at", "updated_at"]

    def get_value(self, obj):
        """Return the appropriate typed value."""
        if obj.value_encrypted:
            # Check if the requesting user has permission to decrypt
            request = self.context.get("request")
            if request and hasattr(request, "user"):
                membership = request.user.memberships.first()
                if membership and membership.role == "admin":
                    try:
                        return get_encryption().decrypt(obj.value_encrypted)
                    except Exception:
                        return "[DECRYPTION_ERROR]"
            return "[REDACTED]"

        if obj.value_json is not None:
            return obj.value_json
        if obj.value_number is not None:
            return float(obj.value_number)
        if obj.value_date is not None:
            return obj.value_date.isoformat()
        if obj.value_datetime is not None:
            return obj.value_datetime.isoformat()
        if obj.value_boolean is not None:
            return obj.value_boolean
        return obj.value_text


class AnswerInputSerializer(serializers.Serializer):
    field_id = serializers.UUIDField()
    value = serializers.JSONField(allow_null=True)


class SurveySubmissionSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = SurveySubmission
        fields = [
            "id", "survey", "survey_version", "respondent", "status",
            "resume_token", "started_at", "last_saved_at", "submitted_at",
            "completion_percentage", "answers",
        ]
        read_only_fields = [
            "id", "survey", "survey_version", "respondent", "status",
            "resume_token", "started_at", "last_saved_at", "submitted_at",
            "completion_percentage",
        ]


class SurveySubmissionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveySubmission
        fields = [
            "id", "survey", "respondent", "status",
            "started_at", "submitted_at", "completion_percentage",
        ]
