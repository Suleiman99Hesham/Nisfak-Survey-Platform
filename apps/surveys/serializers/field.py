from rest_framework import serializers

from apps.surveys.models import FieldOption, SurveyField


class FieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldOption
        fields = ["id", "label", "value", "order", "metadata"]
        read_only_fields = ["id"]


class SurveyFieldSerializer(serializers.ModelSerializer):
    options = FieldOptionSerializer(many=True, read_only=True)

    class Meta:
        model = SurveyField
        fields = [
            "id", "section", "key", "label", "field_type", "required",
            "order", "is_sensitive", "placeholder", "help_text",
            "validation_rules", "default_value", "options",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SurveyFieldCreateSerializer(serializers.ModelSerializer):
    options = FieldOptionSerializer(many=True, required=False)

    class Meta:
        model = SurveyField
        fields = [
            "id", "key", "label", "field_type", "required",
            "order", "is_sensitive", "placeholder", "help_text",
            "validation_rules", "default_value", "options",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        options_data = validated_data.pop("options", [])
        field = SurveyField.objects.create(**validated_data)
        for option_data in options_data:
            FieldOption.objects.create(field=field, **option_data)
        return field

    def update(self, instance, validated_data):
        options_data = validated_data.pop("options", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if options_data is not None:
            instance.options.all().delete()
            for option_data in options_data:
                FieldOption.objects.create(field=instance, **option_data)

        return instance
