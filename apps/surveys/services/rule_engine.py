from typing import Any


class RuleEngine:
    """
    Evaluates visibility rules against a set of answers.
    Used both for determining which fields to show (frontend schema)
    and for backend validation (which fields are visible/required).
    """

    OPERATORS = {
        "eq": lambda a, v: a == v,
        "neq": lambda a, v: a != v,
        "gt": lambda a, v: float(a) > float(v),
        "lt": lambda a, v: float(a) < float(v),
        "gte": lambda a, v: float(a) >= float(v),
        "lte": lambda a, v: float(a) <= float(v),
        "in": lambda a, v: a in v,
        "not_in": lambda a, v: a not in v,
        "contains": lambda a, v: v in str(a),
        "not_contains": lambda a, v: v not in str(a),
        "is_empty": lambda a, v: not a,
        "is_not_empty": lambda a, v: bool(a),
        "between": lambda a, v: float(v[0]) <= float(a) <= float(v[1]),
    }

    def __init__(self, answers: dict[str, Any]):
        """
        Args:
            answers: dict mapping field_id (str UUID) -> answer value
        """
        self.answers = answers

    def evaluate_condition(self, condition) -> bool:
        """
        Evaluate a single VisibilityCondition against the current answers.
        Accepts either a model instance or a dict (from snapshot).
        """
        if isinstance(condition, dict):
            source_field_id = str(condition["source_field_id"])
            operator = condition["operator"]
            expected_value = condition["expected_value"]
        else:
            source_field_id = str(condition.source_field_id)
            operator = condition.operator
            expected_value = condition.expected_value

        actual_answer = self.answers.get(source_field_id)

        if actual_answer is None and operator not in ("is_empty",):
            return False

        op_func = self.OPERATORS.get(operator)
        if not op_func:
            raise ValueError(f"Unknown operator: {operator}")

        try:
            return op_func(actual_answer, expected_value)
        except (TypeError, ValueError):
            return False

    def evaluate_rule(self, rule) -> bool:
        """
        Evaluate a VisibilityRule (all its conditions combined with AND/OR).
        Accepts either a model instance or a dict (from snapshot).
        """
        if isinstance(rule, dict):
            conditions = rule.get("conditions", [])
            logical_operator = rule.get("logical_operator", "AND")
        else:
            conditions = list(rule.conditions.all())
            logical_operator = rule.logical_operator

        if not conditions:
            return True

        results = [self.evaluate_condition(c) for c in conditions]

        if logical_operator == "AND":
            return all(results)
        return any(results)

    def is_visible(self, target_type: str, target_id: str, rules: list) -> bool:
        """
        Determine if a section or field is visible.
        Multiple rules on the same target use OR logic:
        the target is visible if ANY applicable rule passes.
        No applicable rules = always visible.
        """
        applicable = []
        for r in rules:
            if isinstance(r, dict):
                r_type = r.get("target_type")
                r_id = str(r.get("target_id"))
            else:
                r_type = r.target_type
                r_id = str(r.target_id)

            if r_type == target_type and r_id == target_id:
                applicable.append(r)

        if not applicable:
            return True

        return any(self.evaluate_rule(r) for r in applicable)

    def get_visible_fields(self, sections, rules) -> set[str]:
        """
        Given survey sections and rules, return the set of field IDs
        that are currently visible based on the current answers.

        Args:
            sections: list of SurveySection instances or dicts (from snapshot)
            rules: list of VisibilityRule instances or dicts (from snapshot)

        Returns:
            set of visible field ID strings
        """
        visible = set()

        for section in sections:
            if isinstance(section, dict):
                section_id = str(section["id"])
                fields = section.get("fields", [])
            else:
                section_id = str(section.id)
                fields = section.fields.all()

            if not self.is_visible("section", section_id, rules):
                continue

            for field in fields:
                if isinstance(field, dict):
                    field_id = str(field["id"])
                else:
                    field_id = str(field.id)

                if self.is_visible("field", field_id, rules):
                    visible.add(field_id)

        return visible
