import uuid

import factory
from cryptography.fernet import Fernet
from django.test import override_settings
from factory.django import DjangoModelFactory

from apps.accounts.models import Membership, Organization, User
from apps.responses.models import Answer, SurveySubmission
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

# Stable test encryption key
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


# ── Account factories ──────────────────────────


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        password = extracted or "testpass123"
        obj.set_password(password)
        if create:
            obj.save(update_fields=["password"])


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)
    role = Membership.Role.ADMIN


# ── Survey factories ───────────────────────────


class SurveyFactory(DjangoModelFactory):
    class Meta:
        model = Survey

    organization = factory.SubFactory(OrganizationFactory)
    created_by = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Survey {n}")
    description = "Test survey"
    status = Survey.Status.DRAFT


class SurveyVersionFactory(DjangoModelFactory):
    class Meta:
        model = SurveyVersion

    survey = factory.SubFactory(SurveyFactory)
    version_number = 1
    snapshot = factory.LazyAttribute(lambda o: {"sections": [], "visibility_rules": [], "field_dependencies": []})


class SurveySectionFactory(DjangoModelFactory):
    class Meta:
        model = SurveySection

    survey = factory.SubFactory(SurveyFactory)
    title = factory.Sequence(lambda n: f"Section {n}")
    description = ""
    order = factory.Sequence(lambda n: n)


class SurveyFieldFactory(DjangoModelFactory):
    class Meta:
        model = SurveyField

    section = factory.SubFactory(SurveySectionFactory)
    key = factory.Sequence(lambda n: f"field_{n}")
    label = factory.Sequence(lambda n: f"Field {n}")
    field_type = SurveyField.FieldType.TEXT
    required = False
    order = factory.Sequence(lambda n: n)


class FieldOptionFactory(DjangoModelFactory):
    class Meta:
        model = FieldOption

    field = factory.SubFactory(SurveyFieldFactory)
    label = factory.Sequence(lambda n: f"Option {n}")
    value = factory.Sequence(lambda n: f"opt_{n}")
    order = factory.Sequence(lambda n: n)


class VisibilityRuleFactory(DjangoModelFactory):
    class Meta:
        model = VisibilityRule

    survey = factory.SubFactory(SurveyFactory)
    target_type = VisibilityRule.TargetType.FIELD
    target_id = factory.LazyFunction(uuid.uuid4)
    logical_operator = VisibilityRule.LogicalOperator.AND


class VisibilityConditionFactory(DjangoModelFactory):
    class Meta:
        model = VisibilityCondition

    rule = factory.SubFactory(VisibilityRuleFactory)
    source_field = factory.SubFactory(SurveyFieldFactory)
    operator = "eq"
    expected_value = "yes"


class FieldDependencyFactory(DjangoModelFactory):
    class Meta:
        model = FieldDependency

    survey = factory.SubFactory(SurveyFactory)
    source_field = factory.SubFactory(SurveyFieldFactory)
    target_field = factory.SubFactory(SurveyFieldFactory)
    dependency_type = FieldDependency.DependencyType.REQUIRED_IF
    config = factory.LazyFunction(dict)


# ── Response factories ─────────────────────────


class SurveySubmissionFactory(DjangoModelFactory):
    class Meta:
        model = SurveySubmission

    survey = factory.SubFactory(SurveyFactory)
    survey_version = factory.SubFactory(SurveyVersionFactory)
    respondent = factory.SubFactory(UserFactory)
    status = SurveySubmission.Status.IN_PROGRESS
    resume_token = factory.LazyFunction(lambda: uuid.uuid4().hex)


class AnswerFactory(DjangoModelFactory):
    class Meta:
        model = Answer

    submission = factory.SubFactory(SurveySubmissionFactory)
    field = factory.SubFactory(SurveyFieldFactory)
    value_text = "test answer"
