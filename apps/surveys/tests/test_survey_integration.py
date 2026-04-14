import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership
from conftest import (
    FieldOptionFactory,
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


@pytest.fixture
def analyst_user(org):
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.ANALYST)
    return user


@pytest.fixture
def viewer_user(org):
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.DATA_VIEWER)
    return user


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    token = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def analyst_client(analyst_user):
    client = APIClient()
    token = RefreshToken.for_user(analyst_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def viewer_client(viewer_user):
    client = APIClient()
    token = RefreshToken.for_user(viewer_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.mark.django_db
class TestSurveyCRUD:
    def test_create_survey(self, admin_client, org):
        resp = admin_client.post("/api/v1/surveys/", {
            "title": "Customer Feedback",
            "description": "A survey about customer experience",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["title"] == "Customer Feedback"

    def test_list_surveys(self, admin_client, org):
        SurveyFactory(organization=org, title="S1")
        SurveyFactory(organization=org, title="S2")
        resp = admin_client.get("/api/v1/surveys/")
        assert resp.status_code == 200
        assert resp.data["count"] == 2

    def test_get_survey_detail(self, admin_client, org):
        survey = SurveyFactory(organization=org)
        resp = admin_client.get(f"/api/v1/surveys/{survey.id}/")
        assert resp.status_code == 200
        assert resp.data["id"] == str(survey.id)

    def test_update_survey(self, admin_client, org):
        survey = SurveyFactory(organization=org, title="Old Title")
        resp = admin_client.patch(f"/api/v1/surveys/{survey.id}/", {
            "title": "New Title",
        }, format="json")
        assert resp.status_code == 200
        survey.refresh_from_db()
        assert survey.title == "New Title"

    def test_delete_survey_archives_it(self, admin_client, org):
        survey = SurveyFactory(organization=org)
        resp = admin_client.delete(f"/api/v1/surveys/{survey.id}/")
        assert resp.status_code == 204
        survey.refresh_from_db()
        assert survey.status == "archived"


@pytest.mark.django_db
class TestSurveyPublishFlow:
    def test_publish_draft_survey(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user)
        section = SurveySectionFactory(survey=survey, order=0)
        SurveyFieldFactory(section=section, field_type="text", label="Name", order=0)

        resp = admin_client.post(f"/api/v1/surveys/{survey.id}/publish/")
        assert resp.status_code == 200
        assert resp.data["version"] == 1
        survey.refresh_from_db()
        assert survey.status == "published"

    def test_publish_creates_version_snapshot(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user)
        section = SurveySectionFactory(survey=survey, order=0)
        field = SurveyFieldFactory(
            section=section, field_type="dropdown", label="Color", order=0
        )
        FieldOptionFactory(field=field, label="Red", value="red", order=0)
        FieldOptionFactory(field=field, label="Blue", value="blue", order=1)

        admin_client.post(f"/api/v1/surveys/{survey.id}/publish/")

        version = survey.versions.first()
        assert version is not None
        snapshot = version.snapshot
        assert len(snapshot["sections"]) == 1
        assert len(snapshot["sections"][0]["fields"]) == 1
        assert len(snapshot["sections"][0]["fields"][0]["options"]) == 2

    def test_cannot_publish_already_published(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user, status="published")
        resp = admin_client.post(f"/api/v1/surveys/{survey.id}/publish/")
        assert resp.status_code == 400

    def test_archive_published_survey(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user, status="published")
        resp = admin_client.post(f"/api/v1/surveys/{survey.id}/archive/")
        assert resp.status_code == 200
        survey.refresh_from_db()
        assert survey.status == "archived"

    def test_cannot_archive_draft(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user, status="draft")
        resp = admin_client.post(f"/api/v1/surveys/{survey.id}/archive/")
        assert resp.status_code == 400


@pytest.mark.django_db
class TestSurveyDuplicate:
    def test_duplicate_creates_new_survey(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user, title="Original")
        section = SurveySectionFactory(survey=survey, order=0)
        field = SurveyFieldFactory(section=section, field_type="text", label="Q1", order=0)
        FieldOptionFactory(field=field, label="A", value="a", order=0)

        resp = admin_client.post(f"/api/v1/surveys/{survey.id}/duplicate/")
        assert resp.status_code == 201
        assert resp.data["title"] == "Original (Copy)"
        assert resp.data["id"] != str(survey.id)
        assert resp.data["status"] == "draft"


@pytest.mark.django_db
class TestSectionEndpoints:
    def test_create_section(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user)
        resp = admin_client.post(f"/api/v1/surveys/{survey.id}/sections/", {
            "title": "Demographics",
            "description": "Basic info",
            "order": 0,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["title"] == "Demographics"

    def test_list_sections(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user)
        SurveySectionFactory(survey=survey, order=0)
        SurveySectionFactory(survey=survey, order=1)
        resp = admin_client.get(f"/api/v1/surveys/{survey.id}/sections/")
        assert resp.status_code == 200
        assert resp.data["count"] == 2


@pytest.mark.django_db
class TestFieldEndpoints:
    def test_create_field(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user)
        section = SurveySectionFactory(survey=survey, order=0)
        resp = admin_client.post(f"/api/v1/sections/{section.id}/fields/", {
            "key": "full_name",
            "label": "Full Name",
            "field_type": "text",
            "required": True,
            "order": 0,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["key"] == "full_name"

    def test_create_field_with_inline_options(self, admin_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user)
        section = SurveySectionFactory(survey=survey, order=0)
        resp = admin_client.post(f"/api/v1/sections/{section.id}/fields/", {
            "key": "color",
            "label": "Favorite Color",
            "field_type": "dropdown",
            "required": False,
            "order": 0,
            "options": [
                {"label": "Red", "value": "red", "order": 0},
                {"label": "Blue", "value": "blue", "order": 1},
            ],
        }, format="json")
        assert resp.status_code == 201
        assert len(resp.data["options"]) == 2
