from rest_framework import serializers

from apps.surveys.models import FieldDependency, VisibilityCondition, VisibilityRule


class VisibilityConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisibilityCondition
        fields = ["id", "source_field", "operator", "expected_value"]
        read_only_fields = ["id"]


class VisibilityRuleSerializer(serializers.ModelSerializer):
    conditions = VisibilityConditionSerializer(many=True, read_only=True)

    class Meta:
        model = VisibilityRule
        fields = ["id", "survey", "target_type", "target_id", "logical_operator", "conditions"]
        read_only_fields = ["id"]


class VisibilityRuleCreateSerializer(serializers.ModelSerializer):
    conditions = VisibilityConditionSerializer(many=True)

    class Meta:
        model = VisibilityRule
        fields = ["id", "target_type", "target_id", "logical_operator", "conditions"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        conditions_data = validated_data.pop("conditions")
        rule = VisibilityRule.objects.create(**validated_data)
        for condition_data in conditions_data:
            VisibilityCondition.objects.create(rule=rule, **condition_data)
        return rule

    def update(self, instance, validated_data):
        conditions_data = validated_data.pop("conditions", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if conditions_data is not None:
            instance.conditions.all().delete()
            for condition_data in conditions_data:
                VisibilityCondition.objects.create(rule=instance, **condition_data)

        return instance


class FieldDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldDependency
        fields = [
            "id", "survey", "source_field", "target_field",
            "dependency_type", "config",
        ]
        read_only_fields = ["id"]


class FieldDependencyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldDependency
        fields = ["id", "source_field", "target_field", "dependency_type", "config"]
        read_only_fields = ["id"]
