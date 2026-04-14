import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class StaticValidator:
    """
    Level 1: Static field validation.
    Validates individual answer values against their field's type and rules.
    """

    def validate(self, field, value) -> list[str]:
        """
        Validate a single answer value against its field definition.

        Args:
            field: SurveyField instance or dict (from snapshot)
            value: the answer value

        Returns:
            list of error messages (empty = valid)
        """
        if isinstance(field, dict):
            field_type = field["field_type"]
            required = field.get("required", False)
            label = field.get("label", "Field")
            validation_rules = field.get("validation_rules", {})
            options = field.get("options", [])
        else:
            field_type = field.field_type
            required = field.required
            label = field.label
            validation_rules = field.validation_rules or {}
            options = list(field.options.values_list("value", flat=True))

        errors = []

        # Required check
        if required and (value is None or value == "" or value == []):
            errors.append(f"'{label}' is required.")
            return errors

        # Skip further validation if empty and not required
        if value is None or value == "" or value == []:
            return errors

        # Type-specific validation
        type_errors = self._validate_type(field_type, value, label)
        errors.extend(type_errors)
        if type_errors:
            return errors

        # Validation rules
        rule_errors = self._validate_rules(validation_rules, value, label, field_type)
        errors.extend(rule_errors)

        # Options check for choice fields
        if field_type in ("dropdown", "radio"):
            option_values = self._get_option_values(options)
            if str(value) not in option_values:
                errors.append(f"'{label}': invalid option '{value}'.")

        elif field_type == "checkbox":
            if isinstance(value, list):
                option_values = self._get_option_values(options)
                for v in value:
                    if str(v) not in option_values:
                        errors.append(f"'{label}': invalid option '{v}'.")

        return errors

    def _get_option_values(self, options) -> set:
        if not options:
            return set()
        if isinstance(options[0], dict):
            return {str(o["value"]) for o in options}
        return {str(o) for o in options}

    def _validate_type(self, field_type: str, value, label: str) -> list[str]:
        errors = []

        if field_type == "number":
            try:
                Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"'{label}': must be a valid number.")

        elif field_type == "email":
            if not isinstance(value, str) or not re.match(
                r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value
            ):
                errors.append(f"'{label}': must be a valid email address.")

        elif field_type == "date":
            if isinstance(value, str):
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"'{label}': must be a valid date (YYYY-MM-DD).")
            elif not isinstance(value, date):
                errors.append(f"'{label}': must be a valid date.")

        elif field_type == "datetime":
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value)
                except ValueError:
                    errors.append(f"'{label}': must be a valid datetime.")
            elif not isinstance(value, datetime):
                errors.append(f"'{label}': must be a valid datetime.")

        elif field_type == "checkbox":
            if not isinstance(value, list):
                errors.append(f"'{label}': must be a list of selected values.")

        elif field_type == "rating":
            try:
                num = int(value)
                if num < 1 or num > 10:
                    errors.append(f"'{label}': rating must be between 1 and 10.")
            except (TypeError, ValueError):
                errors.append(f"'{label}': must be a valid rating number.")

        return errors

    def _validate_rules(
        self, rules: dict, value, label: str, field_type: str
    ) -> list[str]:
        errors = []

        if "min_length" in rules and isinstance(value, str):
            if len(value) < rules["min_length"]:
                errors.append(
                    f"'{label}': must be at least {rules['min_length']} characters."
                )

        if "max_length" in rules and isinstance(value, str):
            if len(value) > rules["max_length"]:
                errors.append(
                    f"'{label}': must be at most {rules['max_length']} characters."
                )

        if "min_value" in rules and field_type == "number":
            try:
                if Decimal(str(value)) < Decimal(str(rules["min_value"])):
                    errors.append(
                        f"'{label}': must be at least {rules['min_value']}."
                    )
            except (InvalidOperation, TypeError):
                pass

        if "max_value" in rules and field_type == "number":
            try:
                if Decimal(str(value)) > Decimal(str(rules["max_value"])):
                    errors.append(
                        f"'{label}': must be at most {rules['max_value']}."
                    )
            except (InvalidOperation, TypeError):
                pass

        if "pattern" in rules and isinstance(value, str):
            if not re.match(rules["pattern"], value):
                errors.append(
                    f"'{label}': does not match the required pattern."
                )

        return errors
