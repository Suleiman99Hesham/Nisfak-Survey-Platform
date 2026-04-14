import secrets
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.audit.services import log_action
from apps.common.cache import invalidate_survey_caches
from apps.responses.models import Answer, SurveySubmission
from apps.responses.services.encryption import get_encryption
from apps.responses.validators.integrity_validator import IntegrityValidator
from apps.surveys.models import Survey, SurveyField


def start_submission(survey, respondent=None, ip_address=None, user_agent=""):
    """
    Start a new survey submission (draft).
    Creates a SurveySubmission pointing to the latest published version.
    """
    if survey.status != Survey.Status.PUBLISHED:
        raise ValueError("Can only respond to published surveys.")

    version = survey.versions.order_by("-version_number").first()
    if not version:
        raise ValueError("Survey has no published version.")

    submission = SurveySubmission.objects.create(
        survey=survey,
        survey_version=version,
        respondent=respondent,
        resume_token=secrets.token_hex(32),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return submission


def save_answers(submission, answers_data):
    """
    Save or update answers for a submission (auto-save / partial save).

    Args:
        submission: SurveySubmission instance
        answers_data: list of dicts [{"field_id": "uuid", "value": ...}, ...]

    Returns:
        list of saved Answer instances
    """
    if submission.status != SurveySubmission.Status.IN_PROGRESS:
        raise ValueError("Cannot save answers to a finalized submission.")

    saved = []
    for answer_data in answers_data:
        field_id = answer_data["field_id"]
        value = answer_data["value"]

        try:
            field = SurveyField.objects.get(id=field_id)
        except SurveyField.DoesNotExist:
            continue

        answer, _created = Answer.objects.update_or_create(
            submission=submission,
            field=field,
            defaults=_build_answer_defaults(field, value),
        )
        saved.append(answer)

    # Update completion percentage
    _update_completion(submission)

    return saved


def submit_response(submission):
    """
    Finalize a submission: run full 3-level validation,
    clean up hidden field answers, mark as submitted.

    Returns:
        (success: bool, errors: list[str])
    """
    validator = IntegrityValidator(submission)
    errors = validator.validate()

    if errors:
        return False, errors

    # Delete answers for hidden fields (prevent data injection)
    hidden_ids = validator.get_hidden_field_ids()
    if hidden_ids:
        Answer.objects.filter(
            submission=submission,
            field_id__in=hidden_ids,
        ).delete()

    submission.status = SurveySubmission.Status.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.completion_percentage = 100.0
    submission.save(update_fields=["status", "submitted_at", "completion_percentage", "last_saved_at"])

    log_action(
        actor=submission.respondent,
        action="response.submit",
        entity_type="submission",
        entity_id=str(submission.id),
        organization=submission.survey.organization,
        metadata={"survey_id": str(submission.survey_id)},
    )

    invalidate_survey_caches(submission.survey_id)
    return True, []


def _build_answer_defaults(field, value):
    """Build the defaults dict for Answer.update_or_create based on field type."""
    defaults = {
        "value_text": None,
        "value_number": None,
        "value_date": None,
        "value_datetime": None,
        "value_boolean": None,
        "value_json": None,
        "value_encrypted": None,
    }

    if value is None or value == "":
        return defaults

    # Handle sensitive fields
    if field.is_sensitive:
        encryption = get_encryption()
        defaults["value_encrypted"] = encryption.encrypt(str(value))
        defaults["value_text"] = "[ENCRYPTED]"
        return defaults

    field_type = field.field_type

    if field_type in ("text", "textarea", "email", "dropdown", "radio"):
        defaults["value_text"] = str(value)

    elif field_type == "number":
        try:
            defaults["value_number"] = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            defaults["value_text"] = str(value)

    elif field_type == "date":
        defaults["value_date"] = value

    elif field_type == "datetime":
        defaults["value_datetime"] = value

    elif field_type in ("checkbox", "matrix", "file_upload"):
        defaults["value_json"] = value

    elif field_type == "rating":
        try:
            defaults["value_number"] = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            defaults["value_text"] = str(value)

    else:
        defaults["value_text"] = str(value)

    return defaults


def _update_completion(submission):
    """Recalculate and save completion percentage."""
    snapshot = submission.survey_version.snapshot
    total_required = 0
    answered_required = 0

    answered_field_ids = set(
        submission.answers.values_list("field_id", flat=True)
    )

    for section in snapshot.get("sections", []):
        for field in section.get("fields", []):
            if field.get("required"):
                total_required += 1
                if str(field["id"]) in {str(fid) for fid in answered_field_ids}:
                    answered_required += 1

    if total_required > 0:
        submission.completion_percentage = round(
            (answered_required / total_required) * 100, 1
        )
    else:
        # No required fields — base on total fields
        total_fields = sum(
            len(s.get("fields", [])) for s in snapshot.get("sections", [])
        )
        if total_fields > 0:
            submission.completion_percentage = round(
                (len(answered_field_ids) / total_fields) * 100, 1
            )

    submission.save(update_fields=["completion_percentage", "last_saved_at"])
