from datetime import date

import pytest

from apps.responses.validators.static_validator import StaticValidator


@pytest.fixture
def validator():
    return StaticValidator()


def _field(field_type, required=False, label="Test Field", validation_rules=None, options=None):
    """Helper to build a field dict for testing."""
    f = {
        "field_type": field_type,
        "required": required,
        "label": label,
        "validation_rules": validation_rules or {},
        "options": options or [],
    }
    return f


class TestRequiredCheck:
    def test_required_field_missing_value(self, validator):
        errors = validator.validate(_field("text", required=True), None)
        assert len(errors) == 1
        assert "required" in errors[0]

    def test_required_field_empty_string(self, validator):
        errors = validator.validate(_field("text", required=True), "")
        assert len(errors) == 1

    def test_required_field_empty_list(self, validator):
        errors = validator.validate(_field("checkbox", required=True), [])
        assert len(errors) == 1

    def test_required_field_with_value(self, validator):
        errors = validator.validate(_field("text", required=True), "hello")
        assert errors == []

    def test_optional_field_empty_is_ok(self, validator):
        errors = validator.validate(_field("text", required=False), None)
        assert errors == []

    def test_optional_field_empty_string_is_ok(self, validator):
        errors = validator.validate(_field("text", required=False), "")
        assert errors == []


class TestTypeValidation:
    def test_number_valid(self, validator):
        errors = validator.validate(_field("number"), "42.5")
        assert errors == []

    def test_number_invalid(self, validator):
        errors = validator.validate(_field("number"), "not_a_number")
        assert len(errors) == 1
        assert "valid number" in errors[0]

    def test_email_valid(self, validator):
        errors = validator.validate(_field("email"), "user@example.com")
        assert errors == []

    def test_email_invalid(self, validator):
        errors = validator.validate(_field("email"), "not-an-email")
        assert len(errors) == 1
        assert "email" in errors[0]

    def test_email_missing_domain(self, validator):
        errors = validator.validate(_field("email"), "user@")
        assert len(errors) == 1

    def test_date_valid_string(self, validator):
        errors = validator.validate(_field("date"), "2024-01-15")
        assert errors == []

    def test_date_invalid_string(self, validator):
        errors = validator.validate(_field("date"), "15-01-2024")
        assert len(errors) == 1
        assert "date" in errors[0].lower()

    def test_date_valid_object(self, validator):
        errors = validator.validate(_field("date"), date(2024, 1, 15))
        assert errors == []

    def test_datetime_valid_iso(self, validator):
        errors = validator.validate(_field("datetime"), "2024-01-15T10:30:00")
        assert errors == []

    def test_datetime_invalid(self, validator):
        errors = validator.validate(_field("datetime"), "not-a-datetime")
        assert len(errors) == 1

    def test_checkbox_valid_list(self, validator):
        field = _field("checkbox", options=[
            {"value": "a", "label": "A"},
            {"value": "b", "label": "B"},
        ])
        errors = validator.validate(field, ["a", "b"])
        assert errors == []

    def test_checkbox_invalid_not_list(self, validator):
        errors = validator.validate(_field("checkbox"), "single_value")
        assert len(errors) == 1
        assert "list" in errors[0]

    def test_rating_valid(self, validator):
        errors = validator.validate(_field("rating"), 5)
        assert errors == []

    def test_rating_out_of_range_high(self, validator):
        errors = validator.validate(_field("rating"), 11)
        assert len(errors) == 1
        assert "between 1 and 10" in errors[0]

    def test_rating_out_of_range_low(self, validator):
        errors = validator.validate(_field("rating"), 0)
        assert len(errors) == 1

    def test_rating_invalid_type(self, validator):
        errors = validator.validate(_field("rating"), "abc")
        assert len(errors) == 1

    def test_text_always_valid(self, validator):
        errors = validator.validate(_field("text"), "anything goes")
        assert errors == []

    def test_textarea_always_valid(self, validator):
        errors = validator.validate(_field("textarea"), "long text here")
        assert errors == []


class TestValidationRules:
    def test_min_length(self, validator):
        field = _field("text", validation_rules={"min_length": 5})
        assert validator.validate(field, "abc") != []
        assert validator.validate(field, "abcde") == []

    def test_max_length(self, validator):
        field = _field("text", validation_rules={"max_length": 5})
        assert validator.validate(field, "abcdef") != []
        assert validator.validate(field, "abcde") == []

    def test_min_value(self, validator):
        field = _field("number", validation_rules={"min_value": 10})
        assert validator.validate(field, "5") != []
        assert validator.validate(field, "10") == []
        assert validator.validate(field, "15") == []

    def test_max_value(self, validator):
        field = _field("number", validation_rules={"max_value": 100})
        assert validator.validate(field, "101") != []
        assert validator.validate(field, "100") == []
        assert validator.validate(field, "50") == []

    def test_pattern(self, validator):
        field = _field("text", validation_rules={"pattern": r"^\d{3}-\d{4}$"})
        assert validator.validate(field, "123-4567") == []
        assert validator.validate(field, "abc") != []

    def test_combined_rules(self, validator):
        field = _field("text", validation_rules={"min_length": 3, "max_length": 10})
        assert validator.validate(field, "ab") != []
        assert validator.validate(field, "abc") == []
        assert validator.validate(field, "abcdefghijk") != []


class TestOptionValidation:
    def test_dropdown_valid_option(self, validator):
        field = _field("dropdown", options=[
            {"value": "a", "label": "A"},
            {"value": "b", "label": "B"},
        ])
        assert validator.validate(field, "a") == []

    def test_dropdown_invalid_option(self, validator):
        field = _field("dropdown", options=[
            {"value": "a", "label": "A"},
            {"value": "b", "label": "B"},
        ])
        errors = validator.validate(field, "c")
        assert len(errors) == 1
        assert "invalid option" in errors[0]

    def test_radio_valid_option(self, validator):
        field = _field("radio", options=[
            {"value": "yes", "label": "Yes"},
            {"value": "no", "label": "No"},
        ])
        assert validator.validate(field, "yes") == []

    def test_checkbox_valid_options(self, validator):
        field = _field("checkbox", options=[
            {"value": "a", "label": "A"},
            {"value": "b", "label": "B"},
            {"value": "c", "label": "C"},
        ])
        assert validator.validate(field, ["a", "c"]) == []

    def test_checkbox_invalid_option(self, validator):
        field = _field("checkbox", options=[
            {"value": "a", "label": "A"},
            {"value": "b", "label": "B"},
        ])
        errors = validator.validate(field, ["a", "z"])
        assert len(errors) == 1
        assert "invalid option" in errors[0]
        assert "'z'" in errors[0]
