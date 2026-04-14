from django.contrib import admin

from apps.surveys.models import (
    FieldDependency,
    FieldOption,
    Survey,
    SurveyField,
    SurveySection,
    SurveyVersion,
    VisibilityCondition,
    VisibilityRule,
)


class SurveySectionInline(admin.TabularInline):
    model = SurveySection
    extra = 0
    show_change_link = True


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ["title", "organization", "status", "version", "created_at"]
    list_filter = ["status", "organization"]
    search_fields = ["title"]
    inlines = [SurveySectionInline]


class SurveyFieldInline(admin.TabularInline):
    model = SurveyField
    extra = 0
    show_change_link = True


@admin.register(SurveySection)
class SurveySectionAdmin(admin.ModelAdmin):
    list_display = ["title", "survey", "order"]
    list_filter = ["survey"]
    inlines = [SurveyFieldInline]


class FieldOptionInline(admin.TabularInline):
    model = FieldOption
    extra = 0


@admin.register(SurveyField)
class SurveyFieldAdmin(admin.ModelAdmin):
    list_display = ["label", "field_type", "section", "order", "required"]
    list_filter = ["field_type", "required"]
    inlines = [FieldOptionInline]


@admin.register(FieldOption)
class FieldOptionAdmin(admin.ModelAdmin):
    list_display = ["label", "value", "field", "order"]


@admin.register(SurveyVersion)
class SurveyVersionAdmin(admin.ModelAdmin):
    list_display = ["survey", "version_number", "published_at"]
    list_filter = ["survey"]


class VisibilityConditionInline(admin.TabularInline):
    model = VisibilityCondition
    extra = 0


@admin.register(VisibilityRule)
class VisibilityRuleAdmin(admin.ModelAdmin):
    list_display = ["survey", "target_type", "target_id", "logical_operator"]
    list_filter = ["target_type", "logical_operator"]
    inlines = [VisibilityConditionInline]


@admin.register(FieldDependency)
class FieldDependencyAdmin(admin.ModelAdmin):
    list_display = ["survey", "source_field", "target_field", "dependency_type"]
    list_filter = ["dependency_type"]
