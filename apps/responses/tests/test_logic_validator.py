import pytest

from apps.responses.validators.logic_validator import LogicValidator


def _build_context(answers, sections, rules=None, dependencies=None):
    """Helper to build a LogicValidator with snapshot-style dicts."""
    return LogicValidator(
        answers=answers,
        sections=sections,
        rules=rules or [],
        dependencies=dependencies or [],
    )


class TestLogicValidatorVisibility:
    def test_answer_to_hidden_field_flagged(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        rules = [{
            "target_type": "field",
            "target_id": "f2",
            "logical_operator": "AND",
            "conditions": [{"source_field_id": "f1", "operator": "eq", "expected_value": "yes"}],
        }]
        field_map = {
            "f1": {"label": "Q1"},
            "f2": {"label": "Q2"},
        }
        # f1 = "no" so f2 is hidden, but we provide an answer for f2
        validator = _build_context({"f1": "no", "f2": "some answer"}, sections, rules)
        errors = validator.validate(field_map)
        assert any("hidden field" in e for e in errors)

    def test_no_error_when_answering_visible_fields_only(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        rules = [{
            "target_type": "field",
            "target_id": "f2",
            "logical_operator": "AND",
            "conditions": [{"source_field_id": "f1", "operator": "eq", "expected_value": "yes"}],
        }]
        field_map = {"f1": {"label": "Q1"}, "f2": {"label": "Q2"}}
        # f1 = "yes" so f2 is visible
        validator = _build_context({"f1": "yes", "f2": "answer"}, sections, rules)
        errors = validator.validate(field_map)
        assert errors == []


class TestLogicValidatorRequiredIf:
    def test_required_if_triggered_and_missing(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        dependencies = [{
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "required_if",
            "config": {"condition": {"operator": "eq", "value": "yes"}},
        }]
        field_map = {"f1": {"label": "Has Other"}, "f2": {"label": "Specify Other"}}
        # f1 = "yes" triggers required on f2, but f2 is not answered
        validator = _build_context({"f1": "yes"}, sections, dependencies=dependencies)
        errors = validator.validate(field_map)
        assert any("required based on" in e for e in errors)

    def test_required_if_triggered_and_answered(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        dependencies = [{
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "required_if",
            "config": {"condition": {"operator": "eq", "value": "yes"}},
        }]
        field_map = {"f1": {"label": "Has Other"}, "f2": {"label": "Specify Other"}}
        validator = _build_context({"f1": "yes", "f2": "filled in"}, sections, dependencies=dependencies)
        errors = validator.validate(field_map)
        assert errors == []

    def test_required_if_not_triggered(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        dependencies = [{
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "required_if",
            "config": {"condition": {"operator": "eq", "value": "yes"}},
        }]
        field_map = {"f1": {"label": "Has Other"}, "f2": {"label": "Specify Other"}}
        # f1 = "no", so f2 is not required
        validator = _build_context({"f1": "no"}, sections, dependencies=dependencies)
        errors = validator.validate(field_map)
        assert errors == []


class TestLogicValidatorFilteredOptions:
    def test_answer_not_in_filtered_options(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        dependencies = [{
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "options_filter",
            "config": {
                "mapping": {"usa": ["ny", "ca"], "uk": ["london"]},
                "default": [],
            },
        }]
        field_map = {"f1": {"label": "Country"}, "f2": {"label": "City"}}
        # f1 = "usa" so f2 can only be "ny" or "ca", but we answer "london"
        validator = _build_context({"f1": "usa", "f2": "london"}, sections, dependencies=dependencies)
        errors = validator.validate(field_map)
        assert any("not available" in e for e in errors)

    def test_answer_in_filtered_options(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        dependencies = [{
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "options_filter",
            "config": {
                "mapping": {"usa": ["ny", "ca"]},
                "default": [],
            },
        }]
        field_map = {"f1": {"label": "Country"}, "f2": {"label": "City"}}
        validator = _build_context({"f1": "usa", "f2": "ny"}, sections, dependencies=dependencies)
        errors = validator.validate(field_map)
        assert errors == []

    def test_checkbox_filtered_options_invalid(self):
        sections = [{"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}]}]
        dependencies = [{
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "options_filter",
            "config": {
                "mapping": {"usa": ["ny", "ca"]},
                "default": [],
            },
        }]
        field_map = {"f1": {"label": "Country"}, "f2": {"label": "Cities"}}
        # List answer with one invalid option
        validator = _build_context({"f1": "usa", "f2": ["ny", "london"]}, sections, dependencies=dependencies)
        errors = validator.validate(field_map)
        assert any("london" in e and "not available" in e for e in errors)


class TestLogicValidatorGetVisibleFieldIds:
    def test_returns_visible_fields(self):
        sections = [
            {"id": "s1", "fields": [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}]},
        ]
        rules = [{
            "target_type": "field",
            "target_id": "f3",
            "logical_operator": "AND",
            "conditions": [{"source_field_id": "f1", "operator": "eq", "expected_value": "show"}],
        }]
        validator = _build_context({"f1": "hide"}, sections, rules)
        visible = validator.get_visible_field_ids()
        assert "f1" in visible
        assert "f2" in visible
        assert "f3" not in visible
