from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel


class Survey(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.CASCADE, related_name="surveys"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_surveys"
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    settings = models.JSONField(default=dict, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["status", "published_at"]),
        ]

    def __str__(self):
        return self.title


class SurveyVersion(UUIDModel):
    """Frozen snapshot of a survey at publish time. Responses reference this."""
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("survey", "version_number")]
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.survey.title} v{self.version_number}"


class SurveySection(UUIDModel, TimeStampedModel):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        unique_together = [("survey", "order")]

    def __str__(self):
        return f"{self.survey.title} - {self.title}"


class SurveyField(UUIDModel, TimeStampedModel):
    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        TEXTAREA = "textarea", "Textarea"
        NUMBER = "number", "Number"
        EMAIL = "email", "Email"
        DATE = "date", "Date"
        DATETIME = "datetime", "Datetime"
        DROPDOWN = "dropdown", "Dropdown"
        CHECKBOX = "checkbox", "Checkbox"
        RADIO = "radio", "Radio"
        FILE_UPLOAD = "file_upload", "File Upload"
        RATING = "rating", "Rating"
        MATRIX = "matrix", "Matrix"

    section = models.ForeignKey(SurveySection, on_delete=models.CASCADE, related_name="fields")
    key = models.CharField(max_length=100)
    label = models.CharField(max_length=1000)
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField()
    is_sensitive = models.BooleanField(default=False)
    placeholder = models.CharField(max_length=500, blank=True)
    help_text = models.TextField(blank=True)
    validation_rules = models.JSONField(default=dict, blank=True)
    default_value = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("section", "order")]

    def __str__(self):
        return f"{self.label} ({self.field_type})"


class FieldOption(UUIDModel):
    """Options for choice-based fields (dropdown, radio, checkbox)."""
    field = models.ForeignKey(SurveyField, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=500)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("field", "value")]

    def __str__(self):
        return f"{self.label} ({self.value})"


class VisibilityRule(UUIDModel):
    """Controls whether a section or field is shown based on conditions."""
    class TargetType(models.TextChoices):
        SECTION = "section", "Section"
        FIELD = "field", "Field"

    class LogicalOperator(models.TextChoices):
        AND = "AND", "All conditions must be true"
        OR = "OR", "Any condition must be true"

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="visibility_rules")
    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    target_id = models.UUIDField()
    logical_operator = models.CharField(
        max_length=5, choices=LogicalOperator.choices, default=LogicalOperator.AND
    )

    class Meta:
        indexes = [
            models.Index(fields=["survey"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"Rule for {self.target_type}:{self.target_id}"


class VisibilityCondition(UUIDModel):
    """A single condition within a visibility rule."""
    class Operator(models.TextChoices):
        EQ = "eq", "Equals"
        NEQ = "neq", "Not Equals"
        GT = "gt", "Greater Than"
        LT = "lt", "Less Than"
        GTE = "gte", ">="
        LTE = "lte", "<="
        IN = "in", "In List"
        NOT_IN = "not_in", "Not In List"
        CONTAINS = "contains", "Contains"
        NOT_CONTAINS = "not_contains", "Not Contains"
        IS_EMPTY = "is_empty", "Is Empty"
        IS_NOT_EMPTY = "is_not_empty", "Is Not Empty"
        BETWEEN = "between", "Between"

    rule = models.ForeignKey(VisibilityRule, on_delete=models.CASCADE, related_name="conditions")
    source_field = models.ForeignKey(
        SurveyField, on_delete=models.CASCADE, related_name="dependent_conditions"
    )
    operator = models.CharField(max_length=20, choices=Operator.choices)
    expected_value = models.JSONField()

    def __str__(self):
        return f"{self.source_field.key} {self.operator} {self.expected_value}"


class FieldDependency(UUIDModel):
    """Cross-section dependency between fields."""
    class DependencyType(models.TextChoices):
        OPTIONS_FILTER = "options_filter", "Filter target options based on source answer"
        VISIBILITY = "visibility", "Show/hide target based on source answer"
        REQUIRED_IF = "required_if", "Target becomes required based on source answer"
        VALUE_CONSTRAINT = "value_constraint", "Constrain target value based on source answer"

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="field_dependencies")
    source_field = models.ForeignKey(
        SurveyField, on_delete=models.CASCADE, related_name="dependents"
    )
    target_field = models.ForeignKey(
        SurveyField, on_delete=models.CASCADE, related_name="depends_on"
    )
    dependency_type = models.CharField(max_length=20, choices=DependencyType.choices)
    config = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["survey"]),
            models.Index(fields=["source_field"]),
            models.Index(fields=["target_field"]),
        ]

    def __str__(self):
        return f"{self.source_field.key} -> {self.target_field.key} ({self.dependency_type})"
