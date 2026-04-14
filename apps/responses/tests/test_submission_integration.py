import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership
from apps.responses.models import Answer, SurveySubmission
from apps.surveys.models import Survey
from apps.surveys.services.survey_builder import build_survey_snapshot, publish_survey
from conftest import (
    FieldOptionFactory,
    MembershipFactory,
    OrganizationFactory,
    SurveyFactory,
    SurveyFieldFactory,
    SurveySectionFactory,
    UserFactory,
    TEST_ENCRYPTION_KEY,
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
def respondent():
    return UserFactory()


@pytest.fixture
def respondent_client(respondent):
    client = APIClient()
    token = RefreshToken.for_user(respondent)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def anon_client():
    return APIClient()


@pytest.fixture
def published_survey(org, admin_user):
    """Create a complete survey and publish it."""
    survey = SurveyFactory(organization=org, created_by=admin_user)
    section = SurveySectionFactory(survey=survey, title="General", order=0)
    name_field = SurveyFieldFactory(
        section=section, key="name", label="Name",
        field_type="text", required=True, order=0,
    )
    email_field = SurveyFieldFactory(
        section=section, key="email", label="Email",
        field_type="email", required=True, order=1,
    )
    color_field = SurveyFieldFactory(
        section=section, key="color", label="Favorite Color",
        field_type="dropdown", required=False, order=2,
    )
    FieldOptionFactory(field=color_field, label="Red", value="red", order=0)
    FieldOptionFactory(field=color_field, label="Blue", value="blue", order=1)

    publish_survey(survey)
    survey.refresh_from_db()
    return survey, {
        "name": name_field,
        "email": email_field,
        "color": color_field,
    }


@pytest.mark.django_db
class TestPublicSurveyView:
    def test_get_published_survey(self, anon_client, published_survey):
        survey, _ = published_survey
        resp = anon_client.get(f"/api/v1/public/surveys/{survey.id}/")
        assert resp.status_code == 200
        assert resp.data["title"] == survey.title

    def test_get_draft_survey_returns_404(self, anon_client, org, admin_user):
        survey = SurveyFactory(organization=org, created_by=admin_user, status="draft")
        resp = anon_client.get(f"/api/v1/public/surveys/{survey.id}/")
        assert resp.status_code == 404


@pytest.mark.django_db
class TestSubmissionFlow:
    def test_start_submission(self, respondent_client, published_survey):
        survey, _ = published_survey
        resp = respondent_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        assert resp.status_code == 201
        assert resp.data["status"] == "in_progress"
        assert resp.data["resume_token"] is not None

    def test_save_answers(self, respondent_client, published_survey):
        survey, fields = published_survey
        # Start
        start_resp = respondent_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        sub_id = start_resp.data["id"]

        # Save answers
        resp = respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
            {"field_id": str(fields["name"].id), "value": "John Doe"},
            {"field_id": str(fields["email"].id), "value": "john@example.com"},
        ], format="json")
        assert resp.status_code == 200
        assert resp.data["detail"] == "Answers saved."

    def test_save_and_submit(self, respondent_client, published_survey):
        survey, fields = published_survey
        # Start
        start_resp = respondent_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        sub_id = start_resp.data["id"]

        # Save all required answers
        respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
            {"field_id": str(fields["name"].id), "value": "Jane Doe"},
            {"field_id": str(fields["email"].id), "value": "jane@example.com"},
            {"field_id": str(fields["color"].id), "value": "red"},
        ], format="json")

        # Submit
        resp = respondent_client.post(f"/api/v1/public/responses/{sub_id}/submit/")
        assert resp.status_code == 200
        assert resp.data["status"] == "submitted"

    def test_submit_without_required_fields_fails(self, respondent_client, published_survey):
        survey, fields = published_survey
        # Start
        start_resp = respondent_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        sub_id = start_resp.data["id"]

        # Only save optional field
        respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
            {"field_id": str(fields["color"].id), "value": "blue"},
        ], format="json")

        # Submit — should fail validation
        resp = respondent_client.post(f"/api/v1/public/responses/{sub_id}/submit/")
        assert resp.status_code == 400
        assert "errors" in resp.data

    def test_resume_by_token(self, anon_client, published_survey):
        survey, fields = published_survey
        # Start anonymous submission
        resp = anon_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        assert resp.status_code == 201
        token = resp.data["resume_token"]

        # Resume
        resume_resp = anon_client.get(f"/api/v1/public/responses/resume/{token}/")
        assert resume_resp.status_code == 200
        assert resume_resp.data["id"] == resp.data["id"]

    def test_anonymous_save_with_resume_token(self, anon_client, published_survey):
        survey, fields = published_survey
        # Start
        start_resp = anon_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        sub_id = start_resp.data["id"]
        token = start_resp.data["resume_token"]

        # Save answers using resume token header
        resp = anon_client.post(
            f"/api/v1/public/responses/{sub_id}/answers/",
            [{"field_id": str(fields["name"].id), "value": "Anon User"}],
            format="json",
            HTTP_X_RESUME_TOKEN=token,
        )
        assert resp.status_code == 200

    def test_cannot_save_to_submitted_submission(self, respondent_client, published_survey):
        survey, fields = published_survey
        # Start, save, submit
        start_resp = respondent_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        sub_id = start_resp.data["id"]
        respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
            {"field_id": str(fields["name"].id), "value": "Test"},
            {"field_id": str(fields["email"].id), "value": "test@example.com"},
        ], format="json")
        respondent_client.post(f"/api/v1/public/responses/{sub_id}/submit/")

        # Try to save more answers — should fail (submission not found because status != in_progress)
        resp = respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
            {"field_id": str(fields["color"].id), "value": "red"},
        ], format="json")
        assert resp.status_code == 404

    def test_completion_percentage_updates(self, respondent_client, published_survey):
        survey, fields = published_survey
        start_resp = respondent_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
        sub_id = start_resp.data["id"]

        # Save one of two required fields
        respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
            {"field_id": str(fields["name"].id), "value": "Test"},
        ], format="json")

        sub = SurveySubmission.objects.get(id=sub_id)
        assert sub.completion_percentage == 50.0

        # Save the second required field
        respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
            {"field_id": str(fields["email"].id), "value": "test@example.com"},
        ], format="json")

        sub.refresh_from_db()
        assert sub.completion_percentage == 100.0


@pytest.mark.django_db
class TestSensitiveFieldSubmission:
    def test_sensitive_field_encrypted(self, respondent_client, org, admin_user):
        import apps.responses.services.encryption as enc_mod

        with override_settings(ENCRYPTION_KEY=TEST_ENCRYPTION_KEY):
            enc_mod._encryption = None

            survey = SurveyFactory(organization=org, created_by=admin_user)
            section = SurveySectionFactory(survey=survey, order=0)
            ssn_field = SurveyFieldFactory(
                section=section, key="ssn", label="SSN",
                field_type="text", required=True, is_sensitive=True, order=0,
            )
            publish_survey(survey)
            survey.refresh_from_db()

            # Start and save
            start_resp = respondent_client.post(f"/api/v1/public/surveys/{survey.id}/start/")
            sub_id = start_resp.data["id"]
            respondent_client.post(f"/api/v1/public/responses/{sub_id}/answers/", [
                {"field_id": str(ssn_field.id), "value": "123-45-6789"},
            ], format="json")

            # Verify encrypted storage
            answer = Answer.objects.get(submission_id=sub_id, field=ssn_field)
            assert answer.value_text == "[ENCRYPTED]"
            assert answer.value_encrypted is not None

            # Decrypt and verify
            from apps.responses.services.encryption import get_encryption
            enc = get_encryption()
            assert enc.decrypt(bytes(answer.value_encrypted)) == "123-45-6789"

            enc_mod._encryption = None
