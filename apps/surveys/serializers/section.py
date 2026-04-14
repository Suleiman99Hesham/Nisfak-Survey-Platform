from rest_framework import serializers

from apps.surveys.models import SurveySection
from apps.surveys.serializers.field import SurveyFieldSerializer


class SurveySectionSerializer(serializers.ModelSerializer):
    fields = SurveyFieldSerializer(many=True, read_only=True)

    class Meta:
        model = SurveySection
        fields = [
            "id", "survey", "title", "description", "order",
            "fields", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SurveySectionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveySection
        fields = ["id", "title", "description", "order"]
        read_only_fields = ["id"]
