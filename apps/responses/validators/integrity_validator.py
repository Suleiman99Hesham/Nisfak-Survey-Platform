from typing import Any

from apps.responses.validators.logic_validator import LogicValidator
from apps.responses.validators.static_validator import StaticValidator


class IntegrityValidator:
    """
    Level 3: Submission integrity validation.
    Orchestrates static + logic validation and checks overall submission completeness.
    """

    def __init__(self, submission):
        """
        Args:
            submission: SurveySubmission instance
        """
        self.submission = submission

    def validate(self) -> list[str]:
        """
        Full validation for final submission.

        Returns:
            list of error messages (empty = valid)
        """
        errors = []
        submission = self.submission

        # Check submission is still in progress
        if submission.status != "in_progress":
            errors.append("This submission has already been finalized.")
            return errors

        # Load the survey version snapshot
        snapshot = submission.survey_version.snapshot
        sections = snapshot.get("sections", [])
        rules = snapshot.get("visibility_rules", [])
        dependencies = snapshot.get("field_dependencies", [])

        # Build field map and answers dict
        field_map = {}
        for section in sections:
            for field in section.get("fields", []):
                field_map[str(field["id"])] = field

        answers = self._load_answers()

        # Logic validation (visibility, dependencies)
        logic_validator = LogicValidator(answers, sections, rules, dependencies)
        visible_ids = logic_validator.get_visible_field_ids()
        logic_errors = logic_validator.validate(field_map)
        errors.extend(logic_errors)

        # Static validation for each visible field
        static_validator = StaticValidator()
        for field_id in visible_ids:
            field = field_map.get(field_id)
            if not field:
                continue
            value = answers.get(field_id)
            field_errors = static_validator.validate(field, value)
            errors.extend(field_errors)

        # Check all visible required fields have answers
        resolutions = logic_validator.get_dependency_resolutions()
        for field_id in visible_ids:
            field = field_map.get(field_id)
            if not field:
                continue
            is_required = field.get("required", False)
            # Also check dynamic required_if
            dep_resolution = resolutions.get(field_id, {})
            if dep_resolution.get("required"):
                is_required = True
            value = answers.get(field_id)
            if is_required and (value is None or value == "" or value == []):
                errors.append(f"'{field.get('label', field_id)}' is required.")

        return list(set(errors))  # deduplicate

    def _load_answers(self) -> dict[str, Any]:
        """Load all answers for this submission into a dict."""
        answers = {}
        for answer in self.submission.answers.select_related("field").all():
            field_id = str(answer.field_id)
            field_type = answer.field.field_type

            if field_type in ("checkbox", "matrix", "file_upload"):
                answers[field_id] = answer.value_json
            elif field_type == "number":
                answers[field_id] = answer.value_number
            elif field_type == "date":
                answers[field_id] = answer.value_date
            elif field_type == "datetime":
                answers[field_id] = answer.value_datetime
            elif answer.field.is_sensitive and answer.value_encrypted:
                # Don't decrypt during validation — just mark as present
                answers[field_id] = "[ENCRYPTED]"
            else:
                answers[field_id] = answer.value_text

        return answers

    def get_hidden_field_ids(self) -> set[str]:
        """Return field IDs that should NOT have answers (for cleanup)."""
        snapshot = self.submission.survey_version.snapshot
        sections = snapshot.get("sections", [])
        rules = snapshot.get("visibility_rules", [])

        all_field_ids = set()
        for section in sections:
            for field in section.get("fields", []):
                all_field_ids.add(str(field["id"]))

        answers = self._load_answers()
        from apps.surveys.services.rule_engine import RuleEngine
        engine = RuleEngine(answers)
        visible_ids = engine.get_visible_fields(sections, rules)

        return all_field_ids - visible_ids
