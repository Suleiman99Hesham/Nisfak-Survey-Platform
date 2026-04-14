from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership
from apps.analytics.selectors.analytics_selectors import (
    get_field_analytics,
    get_survey_summary,
)
from apps.responses.models import Answer, SurveySubmission
from apps.surveys.services.survey_builder import publish_survey
from conftest import (
    AnswerFactory,
    FieldOptionFactory,
    MembershipFactory,
    OrganizationFactory,
    SurveyFactory,
    SurveyFieldFactory,
    SurveySectionFactory,
    SurveySubmissionFactory,
    UserFactory,
)


@pytest.fixture
def analytics_survey():
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.ADMIN)
    survey = SurveyFactory(organization=org, created_by=user)
    section = SurveySectionFactory(survey=survey, order=0)
    name_field = SurveyFieldFactory(
        section=section, key="name", label="Name",
        field_type="text", required=True, order=0,
    )
    rating_field = SurveyFieldFactory(
        section=section, key="rating", label="Rating",
        field_type="rating", required=False, order=1,
    )
    version = publish_survey(survey)
    return {
        "org": org,
        "user": user,
        "survey": survey,
        "version": version,
        "name_field": name_field,
        "rating_field": rating_field,
    }


def _make_submitted(survey, version, name_field, name_value, rating_field=None, rating_value=None):
    sub = SurveySubmissionFactory(
        survey=survey, survey_version=version,
        status=SurveySubmission.Status.SUBMITTED,
        submitted_at=timezone.now(),
    )
    AnswerFactory(submission=sub, field=name_field, value_text=name_value)
    if rating_field and rating_value is not None:
        AnswerFactory(
            submission=sub, field=rating_field,
            value_text=None, value_number=Decimal(str(rating_value)),
        )
    return sub


@pytest.mark.django_db
class TestSurveySummary:
    def test_empty_survey(self, analytics_survey):
        summary = get_survey_summary(analytics_survey["survey"])
        assert summary["total_submissions"] == 0
        assert summary["completion_rate"] == 0

    def test_with_submissions(self, analytics_survey):
        s = analytics_survey
        _make_submitted(s["survey"], s["version"], s["name_field"], "Alice")
        _make_submitted(s["survey"], s["version"], s["name_field"], "Bob")
        # One in-progress
        SurveySubmissionFactory(
            survey=s["survey"], survey_version=s["version"],
            status=SurveySubmission.Status.IN_PROGRESS,
        )

        summary = get_survey_summary(s["survey"])
        assert summary["total_submissions"] == 3
        assert summary["completed_submissions"] == 2
        assert summary["in_progress_submissions"] == 1
        assert summary["completion_rate"] == pytest.approx(66.7, abs=0.1)


@pytest.mark.django_db
class TestFieldAnalytics:
    def test_text_field_distribution(self, analytics_survey):
        s = analytics_survey
        _make_submitted(s["survey"], s["version"], s["name_field"], "Alice")
        _make_submitted(s["survey"], s["version"], s["name_field"], "Alice")
        _make_submitted(s["survey"], s["version"], s["name_field"], "Bob")

        result = get_field_analytics(s["survey"], s["name_field"].id)
        assert result["total_responses"] == 3
        assert result["distribution"]["Alice"] == 2
        assert result["distribution"]["Bob"] == 1

    def test_rating_field_stats(self, analytics_survey):
        s = analytics_survey
        _make_submitted(s["survey"], s["version"], s["name_field"], "A", s["rating_field"], 3)
        _make_submitted(s["survey"], s["version"], s["name_field"], "B", s["rating_field"], 7)
        _make_submitted(s["survey"], s["version"], s["name_field"], "C", s["rating_field"], 5)

        result = get_field_analytics(s["survey"], s["rating_field"].id)
        assert result["total_responses"] == 3
        assert result["stats"]["average"] == pytest.approx(5.0, abs=0.01)
        assert result["stats"]["min"] == pytest.approx(3.0, abs=0.01)
        assert result["stats"]["max"] == pytest.approx(7.0, abs=0.01)

    def test_empty_field(self, analytics_survey):
        s = analytics_survey
        result = get_field_analytics(s["survey"], s["rating_field"].id)
        assert result["total_responses"] == 0


@pytest.mark.django_db
class TestAnalyticsAPI:
    def test_summary_endpoint(self, analytics_survey):
        s = analytics_survey
        client = APIClient()
        token = RefreshToken.for_user(s["user"])
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        resp = client.get(f"/api/v1/surveys/{s['survey'].id}/analytics/summary/")
        assert resp.status_code == 200
        assert "total_submissions" in resp.data

    def test_field_analytics_endpoint(self, analytics_survey):
        s = analytics_survey
        _make_submitted(s["survey"], s["version"], s["name_field"], "Test")
        client = APIClient()
        token = RefreshToken.for_user(s["user"])
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        resp = client.get(
            f"/api/v1/surveys/{s['survey'].id}/analytics/fields/{s['name_field'].id}/"
        )
        assert resp.status_code == 200
        assert resp.data["total_responses"] == 1
