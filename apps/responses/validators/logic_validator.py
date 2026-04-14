from typing import Any

from apps.surveys.services.dependency_resolver import DependencyResolver
from apps.surveys.services.rule_engine import RuleEngine


class LogicValidator:
    """
    Level 2: Dynamic logic validation.
    Validates answers against visibility rules and field dependencies.
    """

    def __init__(self, answers: dict[str, Any], sections, rules, dependencies):
        """
        Args:
            answers: dict mapping field_id (str) -> answer value
            sections: list of section instances or dicts
            rules: list of VisibilityRule instances or dicts
            dependencies: list of FieldDependency instances or dicts
        """
        self.answers = answers
        self.engine = RuleEngine(answers)
        self.resolver = DependencyResolver(answers)
        self.sections = sections
        self.rules = rules
        self.dependencies = dependencies

    def get_visible_field_ids(self) -> set[str]:
        return self.engine.get_visible_fields(self.sections, self.rules)

    def get_dependency_resolutions(self) -> dict[str, dict]:
        return self.resolver.resolve_all(self.dependencies)

    def validate(self, field_map: dict) -> list[str]:
        """
        Validate answers against dynamic logic.

        Args:
            field_map: dict mapping field_id (str) -> field instance or dict

        Returns:
            list of error messages
        """
        errors = []
        visible_ids = self.get_visible_field_ids()
        resolutions = self.get_dependency_resolutions()

        # Check for answers to hidden fields
        for field_id, value in self.answers.items():
            if field_id not in visible_ids and value is not None:
                label = self._get_label(field_id, field_map)
                errors.append(
                    f"'{label}': answer provided for a hidden field."
                )

        # Check dynamic required (required_if)
        for field_id, resolution in resolutions.items():
            if field_id not in visible_ids:
                continue
            if resolution.get("required") and not self.answers.get(field_id):
                label = self._get_label(field_id, field_map)
                errors.append(f"'{label}': is required based on your previous answers.")

        # Check filtered options
        for field_id, resolution in resolutions.items():
            if field_id not in visible_ids:
                continue
            if "options" in resolution:
                answer = self.answers.get(field_id)
                if answer is not None:
                    allowed = {str(o) if isinstance(o, str) else str(o.get("value", o)) for o in resolution["options"]}
                    if isinstance(answer, list):
                        for v in answer:
                            if str(v) not in allowed:
                                label = self._get_label(field_id, field_map)
                                errors.append(f"'{label}': option '{v}' is not available.")
                    else:
                        if str(answer) not in allowed:
                            label = self._get_label(field_id, field_map)
                            errors.append(f"'{label}': option '{answer}' is not available.")

        return errors

    def _get_label(self, field_id: str, field_map: dict) -> str:
        field = field_map.get(field_id)
        if field is None:
            return f"Field {field_id}"
        if isinstance(field, dict):
            return field.get("label", f"Field {field_id}")
        return field.label
