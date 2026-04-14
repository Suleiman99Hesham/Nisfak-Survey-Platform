from rest_framework import serializers

from apps.surveys.models import Survey, SurveyVersion
from apps.surveys.serializers.rules import (
    FieldDependencySerializer,
    VisibilityRuleSerializer,
)
from apps.surveys.serializers.section import SurveySectionSerializer


class SurveyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    sections_count = serializers.IntegerField(source="sections.count", read_only=True)

    class Meta:
        model = Survey
        fields = [
            "id", "title", "description", "status", "version",
            "sections_count", "created_at", "updated_at", "published_at",
        ]
        read_only_fields = ["id", "status", "version", "created_at", "updated_at", "published_at"]


class SurveyDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested sections, fields, rules, and dependencies."""
    sections = SurveySectionSerializer(many=True, read_only=True)
    visibility_rules = VisibilityRuleSerializer(many=True, read_only=True)
    field_dependencies = FieldDependencySerializer(many=True, read_only=True)

    class Meta:
        model = Survey
        fields = [
            "id", "organization", "created_by", "title", "description",
            "status", "version", "settings", "published_at",
            "sections", "visibility_rules", "field_dependencies",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "created_by", "status", "version",
            "published_at", "created_at", "updated_at",
        ]


class SurveyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Survey
        fields = ["id", "title", "description", "settings"]
        read_only_fields = ["id"]


class SurveyVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyVersion
        fields = ["id", "survey", "version_number", "snapshot", "published_at"]
        read_only_fields = ["id", "published_at"]
