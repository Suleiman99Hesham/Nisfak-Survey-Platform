from django.utils import timezone

from apps.audit.services import log_action
from apps.common.cache import invalidate_survey_caches
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


def build_survey_snapshot(survey):
    """Serialize the full survey structure into a JSON snapshot for versioning."""
    sections = []
    for section in survey.sections.prefetch_related("fields__options").all():
        fields = []
        for field in section.fields.all():
            fields.append({
                "id": str(field.id),
                "key": field.key,
                "label": field.label,
                "field_type": field.field_type,
                "required": field.required,
                "order": field.order,
                "is_sensitive": field.is_sensitive,
                "placeholder": field.placeholder,
                "help_text": field.help_text,
                "validation_rules": field.validation_rules,
                "default_value": field.default_value,
                "options": [
                    {
                        "id": str(opt.id),
                        "label": opt.label,
                        "value": opt.value,
                        "order": opt.order,
                        "metadata": opt.metadata,
                    }
                    for opt in field.options.all()
                ],
            })
        sections.append({
            "id": str(section.id),
            "title": section.title,
            "description": section.description,
            "order": section.order,
            "fields": fields,
        })

    visibility_rules = []
    for rule in survey.visibility_rules.prefetch_related("conditions").all():
        visibility_rules.append({
            "id": str(rule.id),
            "target_type": rule.target_type,
            "target_id": str(rule.target_id),
            "logical_operator": rule.logical_operator,
            "conditions": [
                {
                    "id": str(cond.id),
                    "source_field_id": str(cond.source_field_id),
                    "operator": cond.operator,
                    "expected_value": cond.expected_value,
                }
                for cond in rule.conditions.all()
            ],
        })

    field_dependencies = []
    for dep in survey.field_dependencies.all():
        field_dependencies.append({
            "id": str(dep.id),
            "source_field_id": str(dep.source_field_id),
            "target_field_id": str(dep.target_field_id),
            "dependency_type": dep.dependency_type,
            "config": dep.config,
        })

    return {
        "id": str(survey.id),
        "title": survey.title,
        "description": survey.description,
        "settings": survey.settings,
        "sections": sections,
        "visibility_rules": visibility_rules,
        "field_dependencies": field_dependencies,
    }


def publish_survey(survey):
    """Publish a draft survey: create a frozen version snapshot."""
    if survey.status != Survey.Status.DRAFT:
        raise ValueError("Only draft surveys can be published.")

    snapshot = build_survey_snapshot(survey)
    version = SurveyVersion.objects.create(
        survey=survey,
        version_number=survey.version,
        snapshot=snapshot,
    )
    survey.status = Survey.Status.PUBLISHED
    survey.published_at = timezone.now()
    survey.save(update_fields=["status", "published_at", "updated_at"])

    log_action(
        actor=survey.created_by,
        action="survey.publish",
        entity_type="survey",
        entity_id=str(survey.id),
        metadata={"version": version.version_number},
    )
    invalidate_survey_caches(survey.id)
    return version


def archive_survey(survey):
    """Archive a published survey."""
    if survey.status != Survey.Status.PUBLISHED:
        raise ValueError("Only published surveys can be archived.")
    survey.status = Survey.Status.ARCHIVED
    survey.save(update_fields=["status", "updated_at"])

    log_action(
        actor=survey.created_by,
        action="survey.archive",
        entity_type="survey",
        entity_id=str(survey.id),
    )
    invalidate_survey_caches(survey.id)


def duplicate_survey(survey, user):
    """Clone a survey as a new draft, including sections, fields, options, rules, and dependencies."""
    # Map old IDs to new IDs for rules/dependencies
    section_id_map = {}
    field_id_map = {}

    new_survey = Survey.objects.create(
        organization=survey.organization,
        created_by=user,
        title=f"{survey.title} (Copy)",
        description=survey.description,
        settings=survey.settings,
    )

    for section in survey.sections.prefetch_related("fields__options").all():
        old_section_id = section.id
        new_section = SurveySection.objects.create(
            survey=new_survey,
            title=section.title,
            description=section.description,
            order=section.order,
        )
        section_id_map[str(old_section_id)] = new_section

        for field in section.fields.all():
            old_field_id = field.id
            new_field = SurveyField.objects.create(
                section=new_section,
                key=field.key,
                label=field.label,
                field_type=field.field_type,
                required=field.required,
                order=field.order,
                is_sensitive=field.is_sensitive,
                placeholder=field.placeholder,
                help_text=field.help_text,
                validation_rules=field.validation_rules,
                default_value=field.default_value,
            )
            field_id_map[str(old_field_id)] = new_field

            for option in field.options.all():
                FieldOption.objects.create(
                    field=new_field,
                    label=option.label,
                    value=option.value,
                    order=option.order,
                    metadata=option.metadata,
                )

    # Duplicate visibility rules with remapped IDs
    for rule in survey.visibility_rules.prefetch_related("conditions").all():
        target_id = str(rule.target_id)
        if rule.target_type == "section" and target_id in section_id_map:
            new_target_id = section_id_map[target_id].id
        elif rule.target_type == "field" and target_id in field_id_map:
            new_target_id = field_id_map[target_id].id
        else:
            continue  # skip rules that reference missing targets

        new_rule = VisibilityRule.objects.create(
            survey=new_survey,
            target_type=rule.target_type,
            target_id=new_target_id,
            logical_operator=rule.logical_operator,
        )
        for cond in rule.conditions.all():
            source_id = str(cond.source_field_id)
            if source_id in field_id_map:
                VisibilityCondition.objects.create(
                    rule=new_rule,
                    source_field=field_id_map[source_id],
                    operator=cond.operator,
                    expected_value=cond.expected_value,
                )

    # Duplicate field dependencies with remapped IDs
    for dep in survey.field_dependencies.all():
        source_id = str(dep.source_field_id)
        target_id = str(dep.target_field_id)
        if source_id in field_id_map and target_id in field_id_map:
            FieldDependency.objects.create(
                survey=new_survey,
                source_field=field_id_map[source_id],
                target_field=field_id_map[target_id],
                dependency_type=dep.dependency_type,
                config=dep.config,
            )

    return new_survey
