from typing import Any

from apps.surveys.services.rule_engine import RuleEngine


class DependencyResolver:
    """
    Resolves cross-section field dependencies based on current answers.
    Supports: options_filter, visibility, required_if, value_constraint.
    """

    def __init__(self, answers: dict[str, Any]):
        self.answers = answers

    def resolve(self, dependency) -> dict:
        """
        Resolve a single FieldDependency.
        Accepts either a model instance or a dict (from snapshot).

        Returns a dict describing the resolved state, e.g.:
            {"options": [...]}  for options_filter
            {"required": True}  for required_if
            {"visible": False}  for visibility
            {"constraints": {...}}  for value_constraint
        """
        if isinstance(dependency, dict):
            source_field_id = str(dependency["source_field_id"])
            dep_type = dependency["dependency_type"]
            config = dependency.get("config", {})
        else:
            source_field_id = str(dependency.source_field_id)
            dep_type = dependency.dependency_type
            config = dependency.config

        source_answer = self.answers.get(source_field_id)

        if dep_type == "options_filter":
            return self._resolve_options_filter(source_answer, config)
        elif dep_type == "required_if":
            return self._resolve_required_if(source_answer, config)
        elif dep_type == "visibility":
            return self._resolve_visibility(source_answer, config)
        elif dep_type == "value_constraint":
            return self._resolve_value_constraint(source_answer, config)

        return {}

    def _resolve_options_filter(self, source_answer, config: dict) -> dict:
        mapping = config.get("mapping", {})
        default = config.get("default", [])

        if source_answer is None:
            return {"options": default}

        return {"options": mapping.get(str(source_answer), default)}

    def _resolve_required_if(self, source_answer, config: dict) -> dict:
        condition = config.get("condition", {})
        operator = condition.get("operator", "eq")
        value = condition.get("value")

        op_func = RuleEngine.OPERATORS.get(operator)
        if not op_func or source_answer is None:
            return {"required": False}

        try:
            return {"required": op_func(source_answer, value)}
        except (TypeError, ValueError):
            return {"required": False}

    def _resolve_visibility(self, source_answer, config: dict) -> dict:
        condition = config.get("condition", {})
        operator = condition.get("operator", "eq")
        value = condition.get("value")

        op_func = RuleEngine.OPERATORS.get(operator)
        if not op_func or source_answer is None:
            return {"visible": False}

        try:
            return {"visible": op_func(source_answer, value)}
        except (TypeError, ValueError):
            return {"visible": False}

    def _resolve_value_constraint(self, source_answer, config: dict) -> dict:
        return {"constraints": config, "source_value": source_answer}

    def resolve_all(self, dependencies) -> dict[str, dict]:
        """
        Resolve all dependencies and return a mapping of
        target_field_id -> resolved state.

        Args:
            dependencies: list of FieldDependency instances or dicts

        Returns:
            dict mapping target_field_id -> resolution dict
        """
        results = {}
        for dep in dependencies:
            if isinstance(dep, dict):
                target_id = str(dep["target_field_id"])
            else:
                target_id = str(dep.target_field_id)

            resolution = self.resolve(dep)

            if target_id in results:
                results[target_id].update(resolution)
            else:
                results[target_id] = resolution

        return results
