import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership
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
def other_org():
    return OrganizationFactory(name="Other Org")


def _client_for(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.mark.django_db
class TestRBACMatrix:
    """Verify that each role can/cannot access specific endpoints."""

    def _setup_users(self, org):
        admin = UserFactory()
        MembershipFactory(user=admin, organization=org, role=Membership.Role.ADMIN)
        analyst = UserFactory()
        MembershipFactory(user=analyst, organization=org, role=Membership.Role.ANALYST)
        viewer = UserFactory()
        MembershipFactory(user=viewer, organization=org, role=Membership.Role.DATA_VIEWER)
        return admin, analyst, viewer

    # ── Survey CRUD ──

    def test_admin_can_create_survey(self, org):
        admin, _, _ = self._setup_users(org)
        resp = _client_for(admin).post("/api/v1/surveys/", {
            "title": "Test", "description": "",
        }, format="json")
        assert resp.status_code == 201

    def test_analyst_cannot_create_survey(self, org):
        _, analyst, _ = self._setup_users(org)
        resp = _client_for(analyst).post("/api/v1/surveys/", {
            "title": "Test", "description": "",
        }, format="json")
        assert resp.status_code == 403

    def test_viewer_cannot_create_survey(self, org):
        _, _, viewer = self._setup_users(org)
        resp = _client_for(viewer).post("/api/v1/surveys/", {
            "title": "Test", "description": "",
        }, format="json")
        assert resp.status_code == 403

    def test_analyst_can_list_surveys(self, org):
        admin, analyst, _ = self._setup_users(org)
        SurveyFactory(organization=org, created_by=admin)
        resp = _client_for(analyst).get("/api/v1/surveys/")
        assert resp.status_code == 200

    def test_viewer_cannot_list_surveys(self, org):
        _, _, viewer = self._setup_users(org)
        resp = _client_for(viewer).get("/api/v1/surveys/")
        assert resp.status_code == 403

    # ── Publish/Archive ──

    def test_admin_can_publish(self, org):
        admin, _, _ = self._setup_users(org)
        survey = SurveyFactory(organization=org, created_by=admin)
        SurveySectionFactory(survey=survey, order=0)
        resp = _client_for(admin).post(f"/api/v1/surveys/{survey.id}/publish/")
        assert resp.status_code == 200

    def test_analyst_cannot_publish(self, org):
        admin, analyst, _ = self._setup_users(org)
        survey = SurveyFactory(organization=org, created_by=admin)
        resp = _client_for(analyst).post(f"/api/v1/surveys/{survey.id}/publish/")
        assert resp.status_code == 403

    # ── Analytics ──

    def test_viewer_can_access_analytics(self, org):
        admin, _, viewer = self._setup_users(org)
        survey = SurveyFactory(organization=org, created_by=admin, status="published")
        resp = _client_for(viewer).get(f"/api/v1/surveys/{survey.id}/analytics/summary/")
        assert resp.status_code == 200

    def test_analyst_can_access_analytics(self, org):
        admin, analyst, _ = self._setup_users(org)
        survey = SurveyFactory(organization=org, created_by=admin, status="published")
        resp = _client_for(analyst).get(f"/api/v1/surveys/{survey.id}/analytics/summary/")
        assert resp.status_code == 200

    # ── Submissions ──

    def test_analyst_can_list_submissions(self, org):
        admin, analyst, _ = self._setup_users(org)
        survey = SurveyFactory(organization=org, created_by=admin)
        resp = _client_for(analyst).get(f"/api/v1/surveys/{survey.id}/submissions/")
        assert resp.status_code == 200

    def test_viewer_cannot_list_submissions(self, org):
        admin, _, viewer = self._setup_users(org)
        survey = SurveyFactory(organization=org, created_by=admin)
        resp = _client_for(viewer).get(f"/api/v1/surveys/{survey.id}/submissions/")
        assert resp.status_code == 403

    # ── Audit logs ──

    def test_admin_can_view_audit_logs(self, org):
        admin, _, _ = self._setup_users(org)
        resp = _client_for(admin).get("/api/v1/audit-logs/")
        assert resp.status_code == 200

    def test_analyst_cannot_view_audit_logs(self, org):
        _, analyst, _ = self._setup_users(org)
        resp = _client_for(analyst).get("/api/v1/audit-logs/")
        assert resp.status_code == 403

    def test_viewer_cannot_view_audit_logs(self, org):
        _, _, viewer = self._setup_users(org)
        resp = _client_for(viewer).get("/api/v1/audit-logs/")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestOrgIsolation:
    """Verify users cannot access resources from other organizations."""

    def test_cannot_see_other_org_surveys(self, org, other_org):
        user1 = UserFactory()
        MembershipFactory(user=user1, organization=org, role=Membership.Role.ADMIN)
        user2 = UserFactory()
        MembershipFactory(user=user2, organization=other_org, role=Membership.Role.ADMIN)

        survey = SurveyFactory(organization=other_org, created_by=user2)

        # user1 should not see user2's survey
        resp = _client_for(user1).get(f"/api/v1/surveys/{survey.id}/")
        assert resp.status_code == 404

    def test_cannot_publish_other_org_survey(self, org, other_org):
        user1 = UserFactory()
        MembershipFactory(user=user1, organization=org, role=Membership.Role.ADMIN)
        user2 = UserFactory()
        MembershipFactory(user=user2, organization=other_org, role=Membership.Role.ADMIN)

        survey = SurveyFactory(organization=other_org, created_by=user2)

        resp = _client_for(user1).post(f"/api/v1/surveys/{survey.id}/publish/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestUnauthenticatedAccess:
    def test_unauthenticated_cannot_access_surveys(self):
        client = APIClient()
        resp = client.get("/api/v1/surveys/")
        assert resp.status_code == 401

    def test_unauthenticated_cannot_access_audit_logs(self):
        client = APIClient()
        resp = client.get("/api/v1/audit-logs/")
        assert resp.status_code == 401

    def test_unauthenticated_can_access_public_survey(self, org):
        user = UserFactory()
        MembershipFactory(user=user, organization=org, role=Membership.Role.ADMIN)
        survey = SurveyFactory(organization=org, created_by=user)
        section = SurveySectionFactory(survey=survey, order=0)
        SurveyFieldFactory(section=section, order=0)
        publish_survey(survey)

        client = APIClient()
        resp = client.get(f"/api/v1/public/surveys/{survey.id}/")
        assert resp.status_code == 200
