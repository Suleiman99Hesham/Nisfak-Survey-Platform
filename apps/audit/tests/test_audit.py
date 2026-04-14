import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership
from apps.audit.models import AuditLog
from apps.audit.services import log_action
from apps.surveys.services.survey_builder import publish_survey
from conftest import (
    MembershipFactory,
    OrganizationFactory,
    SurveyFactory,
    SurveyFieldFactory,
    SurveySectionFactory,
    UserFactory,
)


@pytest.fixture
def org():
    return OrganizationFactory()


@pytest.fixture
def admin_user(org):
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.ADMIN)
    return user


@pytest.mark.django_db
class TestAuditLogService:
    def test_log_action_creates_entry(self, org, admin_user):
        log_action(
            actor=admin_user,
            action="test.action",
            entity_type="test",
            entity_id="123",
            metadata={"key": "value"},
        )
        log = AuditLog.objects.filter(action="test.action").first()
        assert log is not None
        assert log.actor == admin_user
        assert log.entity_id == "123"
        assert log.metadata == {"key": "value"}

    def test_publish_creates_audit_log(self, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user)
        SurveySectionFactory(survey=survey, order=0)
        publish_survey(survey)
        log = AuditLog.objects.filter(action="survey.publish").first()
        assert log is not None
        assert log.entity_id == str(survey.id)


@pytest.mark.django_db
class TestAuditLogAPI:
    def test_admin_can_list_audit_logs(self, org, admin_user):
        log_action(
            actor=admin_user,
            action="test.action",
            entity_type="test",
            entity_id="1",
        )
        client = APIClient()
        token = RefreshToken.for_user(admin_user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        resp = client.get("/api/v1/audit-logs/")
        assert resp.status_code == 200

    def test_audit_logs_filterable_by_action(self, org, admin_user):
        log_action(actor=admin_user, action="survey.create", entity_type="survey", entity_id="1")
        log_action(actor=admin_user, action="survey.publish", entity_type="survey", entity_id="1")

        client = APIClient()
        token = RefreshToken.for_user(admin_user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        resp = client.get("/api/v1/audit-logs/?action=survey.publish")
        assert resp.status_code == 200
        # Should only have the publish log (filtered)
        for item in resp.data["results"]:
            assert item["action"] == "survey.publish"
