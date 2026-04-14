import pytest

from apps.responses.models import Answer, SurveySubmission
from apps.responses.validators.integrity_validator import IntegrityValidator
from apps.surveys.services.survey_builder import build_survey_snapshot, publish_survey
from conftest import (
    AnswerFactory,
    FieldOptionFactory,
    OrganizationFactory,
    SurveyFactory,
    SurveyFieldFactory,
    SurveySectionFactory,
    SurveySubmissionFactory,
    SurveyVersionFactory,
    UserFactory,
    VisibilityConditionFactory,
    VisibilityRuleFactory,
)


@pytest.fixture
def simple_survey():
    """Survey with one section: required name, required email, optional color dropdown."""
    org = OrganizationFactory()
    user = UserFactory()
    survey = SurveyFactory(organization=org, created_by=user)
    section = SurveySectionFactory(survey=survey, order=0)
    name = SurveyFieldFactory(
        section=section, key="name", label="Name",
        field_type="text", required=True, order=0,
    )
    email = SurveyFieldFactory(
        section=section, key="email", label="Email",
        field_type="email", required=True, order=1,
    )
    color = SurveyFieldFactory(
        section=section, key="color", label="Color",
        field_type="dropdown", required=False, order=2,
    )
    FieldOptionFactory(field=color, label="Red", value="red", order=0)
    FieldOptionFactory(field=color, label="Blue", value="blue", order=1)

    version = publish_survey(survey)
    return survey, version, {"name": name, "email": email, "color": color}


@pytest.mark.django_db
class TestIntegrityValidator:
    def test_valid_submission(self, simple_survey):
        survey, version, fields = simple_survey
        sub = SurveySubmissionFactory(survey=survey, survey_version=version)
        AnswerFactory(submission=sub, field=fields["name"], value_text="John")
        AnswerFactory(submission=sub, field=fields["email"], value_text="john@example.com")

        validator = IntegrityValidator(sub)
        errors = validator.validate()
        assert errors == []

    def test_missing_required_field(self, simple_survey):
        survey, version, fields = simple_survey
        sub = SurveySubmissionFactory(survey=survey, survey_version=version)
        # Only provide name, skip email
        AnswerFactory(submission=sub, field=fields["name"], value_text="John")

        validator = IntegrityValidator(sub)
        errors = validator.validate()
        assert any("Email" in e and "required" in e for e in errors)

    def test_invalid_email_format(self, simple_survey):
        survey, version, fields = simple_survey
        sub = SurveySubmissionFactory(survey=survey, survey_version=version)
        AnswerFactory(submission=sub, field=fields["name"], value_text="John")
        AnswerFactory(submission=sub, field=fields["email"], value_text="not-an-email")

        validator = IntegrityValidator(sub)
        errors = validator.validate()
        assert any("email" in e.lower() for e in errors)

    def test_already_submitted(self, simple_survey):
        survey, version, fields = simple_survey
        sub = SurveySubmissionFactory(
            survey=survey, survey_version=version,
            status=SurveySubmission.Status.SUBMITTED,
        )
        validator = IntegrityValidator(sub)
        errors = validator.validate()
        assert any("finalized" in e for e in errors)

    def test_get_hidden_field_ids(self):
        """Fields hidden by visibility rules should be returned by get_hidden_field_ids."""
        org = OrganizationFactory()
        user = UserFactory()
        survey = SurveyFactory(organization=org, created_by=user)
        section = SurveySectionFactory(survey=survey, order=0)
        trigger = SurveyFieldFactory(
            section=section, key="trigger", label="Trigger",
            field_type="text", required=False, order=0,
        )
        conditional = SurveyFieldFactory(
            section=section, key="details", label="Details",
            field_type="text", required=False, order=1,
        )
        # Rule: show "details" only when trigger == "yes"
        rule = VisibilityRuleFactory(
            survey=survey, target_type="field",
            target_id=conditional.id, logical_operator="AND",
        )
        VisibilityConditionFactory(
            rule=rule, source_field=trigger,
            operator="eq", expected_value="yes",
        )

        version = publish_survey(survey)
        sub = SurveySubmissionFactory(survey=survey, survey_version=version)
        # Trigger = "no", so "details" should be hidden
        AnswerFactory(submission=sub, field=trigger, value_text="no")

        validator = IntegrityValidator(sub)
        hidden = validator.get_hidden_field_ids()
        assert str(conditional.id) in hidden
        assert str(trigger.id) not in hidden
