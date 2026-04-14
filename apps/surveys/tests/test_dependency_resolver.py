import pytest

from apps.surveys.services.dependency_resolver import DependencyResolver


class TestOptionsFilter:
    def test_returns_mapped_options(self):
        resolver = DependencyResolver({"f1": "usa"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "options_filter",
            "config": {
                "mapping": {
                    "usa": ["ny", "ca", "tx"],
                    "uk": ["london", "manchester"],
                },
                "default": ["other"],
            },
        }
        result = resolver.resolve(dep)
        assert result == {"options": ["ny", "ca", "tx"]}

    def test_returns_default_when_no_mapping_match(self):
        resolver = DependencyResolver({"f1": "france"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "options_filter",
            "config": {
                "mapping": {"usa": ["ny"]},
                "default": ["other"],
            },
        }
        result = resolver.resolve(dep)
        assert result == {"options": ["other"]}

    def test_returns_default_when_source_is_none(self):
        resolver = DependencyResolver({})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "options_filter",
            "config": {"mapping": {"usa": ["ny"]}, "default": ["fallback"]},
        }
        result = resolver.resolve(dep)
        assert result == {"options": ["fallback"]}


class TestRequiredIf:
    def test_required_when_condition_met(self):
        resolver = DependencyResolver({"f1": "yes"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "required_if",
            "config": {"condition": {"operator": "eq", "value": "yes"}},
        }
        result = resolver.resolve(dep)
        assert result == {"required": True}

    def test_not_required_when_condition_not_met(self):
        resolver = DependencyResolver({"f1": "no"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "required_if",
            "config": {"condition": {"operator": "eq", "value": "yes"}},
        }
        result = resolver.resolve(dep)
        assert result == {"required": False}

    def test_not_required_when_source_missing(self):
        resolver = DependencyResolver({})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "required_if",
            "config": {"condition": {"operator": "eq", "value": "yes"}},
        }
        result = resolver.resolve(dep)
        assert result == {"required": False}

    def test_required_if_with_neq(self):
        resolver = DependencyResolver({"f1": "other"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "required_if",
            "config": {"condition": {"operator": "neq", "value": "skip"}},
        }
        result = resolver.resolve(dep)
        assert result == {"required": True}


class TestVisibilityDependency:
    def test_visible_when_condition_met(self):
        resolver = DependencyResolver({"f1": "show"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "visibility",
            "config": {"condition": {"operator": "eq", "value": "show"}},
        }
        result = resolver.resolve(dep)
        assert result == {"visible": True}

    def test_hidden_when_condition_not_met(self):
        resolver = DependencyResolver({"f1": "hide"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "visibility",
            "config": {"condition": {"operator": "eq", "value": "show"}},
        }
        result = resolver.resolve(dep)
        assert result == {"visible": False}

    def test_hidden_when_source_missing(self):
        resolver = DependencyResolver({})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "visibility",
            "config": {"condition": {"operator": "eq", "value": "show"}},
        }
        result = resolver.resolve(dep)
        assert result == {"visible": False}


class TestValueConstraint:
    def test_returns_config_and_source_value(self):
        resolver = DependencyResolver({"f1": 100})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "value_constraint",
            "config": {"max_value": "source"},
        }
        result = resolver.resolve(dep)
        assert result == {"constraints": {"max_value": "source"}, "source_value": 100}

    def test_source_value_none_when_missing(self):
        resolver = DependencyResolver({})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "value_constraint",
            "config": {"min_value": 0},
        }
        result = resolver.resolve(dep)
        assert result["source_value"] is None


class TestResolveAll:
    def test_resolves_multiple_dependencies(self):
        resolver = DependencyResolver({"f1": "yes", "f2": "usa"})
        deps = [
            {
                "source_field_id": "f1",
                "target_field_id": "f3",
                "dependency_type": "required_if",
                "config": {"condition": {"operator": "eq", "value": "yes"}},
            },
            {
                "source_field_id": "f2",
                "target_field_id": "f4",
                "dependency_type": "options_filter",
                "config": {"mapping": {"usa": ["ny", "ca"]}, "default": []},
            },
        ]
        results = resolver.resolve_all(deps)
        assert results["f3"] == {"required": True}
        assert results["f4"] == {"options": ["ny", "ca"]}

    def test_merges_multiple_deps_on_same_target(self):
        resolver = DependencyResolver({"f1": "yes", "f2": "show"})
        deps = [
            {
                "source_field_id": "f1",
                "target_field_id": "f3",
                "dependency_type": "required_if",
                "config": {"condition": {"operator": "eq", "value": "yes"}},
            },
            {
                "source_field_id": "f2",
                "target_field_id": "f3",
                "dependency_type": "visibility",
                "config": {"condition": {"operator": "eq", "value": "show"}},
            },
        ]
        results = resolver.resolve_all(deps)
        assert results["f3"]["required"] is True
        assert results["f3"]["visible"] is True

    def test_unknown_dependency_type_returns_empty(self):
        resolver = DependencyResolver({"f1": "test"})
        dep = {
            "source_field_id": "f1",
            "target_field_id": "f2",
            "dependency_type": "unknown_type",
            "config": {},
        }
        result = resolver.resolve(dep)
        assert result == {}
