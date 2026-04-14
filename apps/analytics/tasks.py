import csv
import io
from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, max_retries=3)
def generate_export(self, export_id):
    """Generate a CSV/XLSX/PDF export file for survey responses."""
    from apps.analytics.models import ReportExport
    from apps.responses.models import Answer, SurveySubmission

    try:
        export = ReportExport.objects.select_related("survey").get(id=export_id)
    except ReportExport.DoesNotExist:
        return

    export.status = "processing"
    export.save(update_fields=["status"])

    try:
        survey = export.survey
        submissions = SurveySubmission.objects.filter(
            survey=survey, status="submitted"
        ).prefetch_related("answers__field")

        # Apply date filters if provided
        filters = export.filters or {}
        if "date_from" in filters:
            submissions = submissions.filter(submitted_at__gte=filters["date_from"])
        if "date_to" in filters:
            submissions = submissions.filter(submitted_at__lte=filters["date_to"])

        if export.export_format == "csv":
            _generate_csv(export, survey, submissions)
        # xlsx and pdf can be implemented with openpyxl and reportlab respectively
        else:
            # Fallback to CSV for now
            _generate_csv(export, survey, submissions)

        export.status = "completed"
        export.completed_at = timezone.now()
        export.save(update_fields=["status", "completed_at"])

    except Exception as exc:
        export.status = "failed"
        export.error_message = str(exc)
        export.save(update_fields=["status", "error_message"])
        raise self.retry(exc=exc, countdown=60)


def _generate_csv(export, survey, submissions):
    """Generate a CSV file from survey submissions."""
    from django.core.files.base import ContentFile

    # Get all field labels from the latest version snapshot
    version = survey.versions.order_by("-version_number").first()
    if not version:
        raise ValueError("Survey has no published version.")

    snapshot = version.snapshot
    field_columns = []
    for section in snapshot.get("sections", []):
        for field in section.get("fields", []):
            field_columns.append({
                "id": field["id"],
                "label": field["label"],
                "key": field.get("key", field["label"]),
            })

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    headers = ["Submission ID", "Respondent", "Status", "Submitted At"]
    headers.extend([f["label"] for f in field_columns])
    writer.writerow(headers)

    # Data rows
    for submission in submissions:
        answers_map = {
            str(a.field_id): a for a in submission.answers.all()
        }
        row = [
            str(submission.id),
            str(submission.respondent_id or "Anonymous"),
            submission.status,
            str(submission.submitted_at or ""),
        ]
        for fc in field_columns:
            answer = answers_map.get(fc["id"])
            if answer:
                if answer.value_encrypted:
                    row.append("[ENCRYPTED]")
                elif answer.value_json is not None:
                    row.append(str(answer.value_json))
                elif answer.value_number is not None:
                    row.append(str(answer.value_number))
                elif answer.value_date is not None:
                    row.append(str(answer.value_date))
                elif answer.value_boolean is not None:
                    row.append(str(answer.value_boolean))
                else:
                    row.append(answer.value_text or "")
            else:
                row.append("")
        writer.writerow(row)

    content = output.getvalue().encode("utf-8")
    filename = f"export_{export.id}.csv"
    export.file_path.save(filename, ContentFile(content), save=True)


@shared_task(bind=True, max_retries=3)
def send_invitation_batch(self, batch_id):
    """Send all pending invitations in a batch via email, in chunks of 50."""
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    from apps.analytics.models import SurveyInvitation

    pending = SurveyInvitation.objects.filter(
        batch_id=batch_id, status=SurveyInvitation.Status.PENDING
    ).select_related("survey")

    sent = 0
    failed = 0
    chunk = []
    for invitation in pending.iterator(chunk_size=50):
        try:
            link = f"{django_settings.PUBLIC_BASE_URL}/s/{invitation.survey_id}?t={invitation.token}"
            send_mail(
                subject=f"You're invited: {invitation.survey.title}",
                message=f"Please complete our survey: {link}",
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[invitation.email],
                fail_silently=False,
            )
            invitation.status = SurveyInvitation.Status.SENT
            invitation.sent_at = timezone.now()
            invitation.save(update_fields=["status", "sent_at"])
            sent += 1
        except Exception as exc:
            invitation.status = SurveyInvitation.Status.FAILED
            invitation.error_message = str(exc)[:2000]
            invitation.save(update_fields=["status", "error_message"])
            failed += 1

    return f"Batch {batch_id}: sent={sent} failed={failed}"


@shared_task
def cleanup_stale_drafts():
    """Delete draft submissions older than 30 days. Runs daily via Celery Beat."""
    from apps.responses.models import SurveySubmission

    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = SurveySubmission.objects.filter(
        status="in_progress",
        last_saved_at__lt=cutoff,
    ).delete()
    return f"Deleted {deleted} stale draft submissions."
