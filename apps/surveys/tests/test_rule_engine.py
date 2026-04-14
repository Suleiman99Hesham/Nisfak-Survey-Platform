import uuid

import pytest

from apps.surveys.services.rule_engine import RuleEngine


class TestRuleEngineOperators:
    """Test all 13 operators with various inputs."""

    def test_eq_match(self):
        engine = RuleEngine({"f1": "yes"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "eq", "expected_value": "yes"}) is True

    def test_eq_no_match(self):
        engine = RuleEngine({"f1": "no"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "eq", "expected_value": "yes"}) is False

    def test_eq_numeric(self):
        engine = RuleEngine({"f1": 42})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "eq", "expected_value": 42}) is True

    def test_neq_match(self):
        engine = RuleEngine({"f1": "no"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "neq", "expected_value": "yes"}) is True

    def test_neq_no_match(self):
        engine = RuleEngine({"f1": "yes"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "neq", "expected_value": "yes"}) is False

    def test_gt(self):
        engine = RuleEngine({"f1": "10"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "gt", "expected_value": "5"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "gt", "expected_value": "10"}) is False
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "gt", "expected_value": "15"}) is False

    def test_lt(self):
        engine = RuleEngine({"f1": "3"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "lt", "expected_value": "5"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "lt", "expected_value": "3"}) is False

    def test_gte(self):
        engine = RuleEngine({"f1": "10"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "gte", "expected_value": "10"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "gte", "expected_value": "5"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "gte", "expected_value": "15"}) is False

    def test_lte(self):
        engine = RuleEngine({"f1": "10"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "lte", "expected_value": "10"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "lte", "expected_value": "15"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "lte", "expected_value": "5"}) is False

    def test_in_operator(self):
        engine = RuleEngine({"f1": "b"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "in", "expected_value": ["a", "b", "c"]}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "in", "expected_value": ["x", "y"]}) is False

    def test_not_in_operator(self):
        engine = RuleEngine({"f1": "z"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "not_in", "expected_value": ["a", "b"]}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "not_in", "expected_value": ["z", "y"]}) is False

    def test_contains(self):
        engine = RuleEngine({"f1": "hello world"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "contains", "expected_value": "world"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "contains", "expected_value": "xyz"}) is False

    def test_not_contains(self):
        engine = RuleEngine({"f1": "hello world"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "not_contains", "expected_value": "xyz"}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "not_contains", "expected_value": "hello"}) is False

    def test_is_empty_true(self):
        engine = RuleEngine({"f1": ""})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "is_empty", "expected_value": None}) is True

    def test_is_empty_false(self):
        engine = RuleEngine({"f1": "something"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "is_empty", "expected_value": None}) is False

    def test_is_empty_none_answer(self):
        engine = RuleEngine({})
        # is_empty is special — None answer should be considered empty
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "is_empty", "expected_value": None}) is True

    def test_is_not_empty(self):
        engine = RuleEngine({"f1": "something"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "is_not_empty", "expected_value": None}) is True

    def test_is_not_empty_when_empty(self):
        engine = RuleEngine({"f1": ""})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "is_not_empty", "expected_value": None}) is False

    def test_between(self):
        engine = RuleEngine({"f1": "5"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "between", "expected_value": [1, 10]}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "between", "expected_value": [1, 5]}) is True
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "between", "expected_value": [6, 10]}) is False

    def test_between_boundaries(self):
        engine = RuleEngine({"f1": "1"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "between", "expected_value": [1, 10]}) is True
        engine2 = RuleEngine({"f1": "10"})
        assert engine2.evaluate_condition({"source_field_id": "f1", "operator": "between", "expected_value": [1, 10]}) is True


class TestRuleEngineEdgeCases:
    """Edge cases: missing answers, type errors, unknown operators."""

    def test_missing_answer_returns_false(self):
        engine = RuleEngine({})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "eq", "expected_value": "yes"}) is False

    def test_type_error_returns_false(self):
        engine = RuleEngine({"f1": "not_a_number"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "gt", "expected_value": "5"}) is False

    def test_unknown_operator_raises(self):
        engine = RuleEngine({"f1": "test"})
        with pytest.raises(ValueError, match="Unknown operator"):
            engine.evaluate_condition({"source_field_id": "f1", "operator": "invalid_op", "expected_value": "x"})

    def test_none_answer_with_non_is_empty_operator(self):
        engine = RuleEngine({"f1": None})
        # None answer with operator other than is_empty should return False
        # (the engine checks `actual_answer is None` and returns False for non-is_empty)
        # But f1 is set to None, which is not the same as missing key
        # The code checks `self.answers.get(source_field_id)` — None is returned
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "eq", "expected_value": None}) is False

    def test_between_with_non_numeric_returns_false(self):
        engine = RuleEngine({"f1": "abc"})
        assert engine.evaluate_condition({"source_field_id": "f1", "operator": "between", "expected_value": [1, 10]}) is False


class TestRuleEngineRuleEvaluation:
    """Test evaluate_rule with AND/OR logic."""

    def test_and_all_true(self):
        engine = RuleEngine({"f1": "yes", "f2": "no"})
        rule = {
            "logical_operator": "AND",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
                {"source_field_id": "f2", "operator": "eq", "expected_value": "no"},
            ],
        }
        assert engine.evaluate_rule(rule) is True

    def test_and_one_false(self):
        engine = RuleEngine({"f1": "yes", "f2": "yes"})
        rule = {
            "logical_operator": "AND",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
                {"source_field_id": "f2", "operator": "eq", "expected_value": "no"},
            ],
        }
        assert engine.evaluate_rule(rule) is False

    def test_or_one_true(self):
        engine = RuleEngine({"f1": "yes", "f2": "yes"})
        rule = {
            "logical_operator": "OR",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
                {"source_field_id": "f2", "operator": "eq", "expected_value": "no"},
            ],
        }
        assert engine.evaluate_rule(rule) is True

    def test_or_all_false(self):
        engine = RuleEngine({"f1": "no", "f2": "no"})
        rule = {
            "logical_operator": "OR",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
                {"source_field_id": "f2", "operator": "eq", "expected_value": "yes"},
            ],
        }
        assert engine.evaluate_rule(rule) is False

    def test_empty_conditions_returns_true(self):
        engine = RuleEngine({})
        rule = {"logical_operator": "AND", "conditions": []}
        assert engine.evaluate_rule(rule) is True

    def test_default_logical_operator_is_and(self):
        engine = RuleEngine({"f1": "yes", "f2": "no"})
        rule = {
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
                {"source_field_id": "f2", "operator": "eq", "expected_value": "no"},
            ],
        }
        assert engine.evaluate_rule(rule) is True


class TestRuleEngineVisibility:
    """Test is_visible and get_visible_fields."""

    def test_no_rules_means_visible(self):
        engine = RuleEngine({})
        assert engine.is_visible("field", "some-id", []) is True

    def test_field_hidden_when_rule_fails(self):
        engine = RuleEngine({"f1": "no"})
        rules = [{
            "target_type": "field",
            "target_id": "target-1",
            "logical_operator": "AND",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
            ],
        }]
        assert engine.is_visible("field", "target-1", rules) is False

    def test_field_shown_when_rule_passes(self):
        engine = RuleEngine({"f1": "yes"})
        rules = [{
            "target_type": "field",
            "target_id": "target-1",
            "logical_operator": "AND",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
            ],
        }]
        assert engine.is_visible("field", "target-1", rules) is True

    def test_multiple_rules_or_logic(self):
        """Multiple rules on the same target use OR logic — visible if ANY passes."""
        engine = RuleEngine({"f1": "no", "f2": "yes"})
        rules = [
            {
                "target_type": "field",
                "target_id": "target-1",
                "logical_operator": "AND",
                "conditions": [
                    {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
                ],
            },
            {
                "target_type": "field",
                "target_id": "target-1",
                "logical_operator": "AND",
                "conditions": [
                    {"source_field_id": "f2", "operator": "eq", "expected_value": "yes"},
                ],
            },
        ]
        assert engine.is_visible("field", "target-1", rules) is True

    def test_section_visibility(self):
        engine = RuleEngine({"f1": "no"})
        rules = [{
            "target_type": "section",
            "target_id": "sec-1",
            "logical_operator": "AND",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
            ],
        }]
        assert engine.is_visible("section", "sec-1", rules) is False

    def test_get_visible_fields_with_snapshot_dicts(self):
        """Test get_visible_fields using dict-based sections (snapshot format)."""
        sections = [
            {
                "id": "sec-1",
                "fields": [
                    {"id": "f1"},
                    {"id": "f2"},
                ],
            },
            {
                "id": "sec-2",
                "fields": [
                    {"id": "f3"},
                ],
            },
        ]
        rules = [{
            "target_type": "field",
            "target_id": "f2",
            "logical_operator": "AND",
            "conditions": [
                {"source_field_id": "f1", "operator": "eq", "expected_value": "yes"},
            ],
        }]
        engine = RuleEngine({"f1": "no"})
        visible = engine.get_visible_fields(sections, rules)
        assert visible == {"f1", "f3"}

    def test_hidden_section_hides_all_fields(self):
        sections = [
            {
                "id": "sec-1",
                "fields": [
                    {"id": "f1"},
                    {"id": "f2"},
                ],
            },
        ]
        rules = [{
            "target_type": "section",
            "target_id": "sec-1",
            "logical_operator": "AND",
            "conditions": [
                {"source_field_id": "trigger", "operator": "eq", "expected_value": "show"},
            ],
        }]
        engine = RuleEngine({"trigger": "hide"})
        visible = engine.get_visible_fields(sections, rules)
        assert visible == set()

    def test_get_visible_fields_no_rules(self):
        sections = [
            {"id": "sec-1", "fields": [{"id": "f1"}, {"id": "f2"}]},
        ]
        engine = RuleEngine({})
        visible = engine.get_visible_fields(sections, [])
        assert visible == {"f1", "f2"}
