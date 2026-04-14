from collections import Counter

from django.db.models import Avg, Count, Max, Min, Q

from apps.responses.models import Answer, SurveySubmission


def get_survey_summary(survey):
    """
    Get aggregated analytics summary for a survey.

    Returns dict with:
        - total_submissions
        - completed_submissions
        - in_progress_submissions
        - completion_rate
        - avg_completion_time (seconds)
    """
    submissions = SurveySubmission.objects.filter(survey=survey)

    total = submissions.count()
    completed = submissions.filter(status="submitted").count()
    in_progress = submissions.filter(status="in_progress").count()

    completion_rate = (completed / total * 100) if total > 0 else 0

    # Average completion time for submitted responses
    submitted = submissions.filter(
        status="submitted",
        submitted_at__isnull=False,
    )
    avg_time = None
    if submitted.exists():
        from django.db.models import F, ExpressionWrapper, DurationField
        durations = submitted.annotate(
            duration=ExpressionWrapper(
                F("submitted_at") - F("started_at"),
                output_field=DurationField(),
            )
        ).aggregate(avg=Avg("duration"))
        if durations["avg"]:
            avg_time = durations["avg"].total_seconds()

    return {
        "total_submissions": total,
        "completed_submissions": completed,
        "in_progress_submissions": in_progress,
        "completion_rate": round(completion_rate, 1),
        "avg_completion_time_seconds": avg_time,
    }


def get_field_analytics(survey, field_id):
    """
    Get per-field analytics breakdown.

    Returns dict with response distribution, basic stats, etc.
    """
    answers = Answer.objects.filter(
        submission__survey=survey,
        submission__status="submitted",
        field_id=field_id,
    )

    total_responses = answers.count()
    if total_responses == 0:
        return {"total_responses": 0, "distribution": {}}

    # Get the field type from the first answer
    first_answer = answers.select_related("field").first()
    field_type = first_answer.field.field_type if first_answer else None

    result = {"total_responses": total_responses}

    if field_type in ("number", "rating"):
        stats = answers.aggregate(
            avg=Avg("value_number"),
            min=Min("value_number"),
            max=Max("value_number"),
        )
        result["stats"] = {
            "average": float(stats["avg"]) if stats["avg"] else None,
            "min": float(stats["min"]) if stats["min"] else None,
            "max": float(stats["max"]) if stats["max"] else None,
        }

    if field_type in ("dropdown", "radio", "text", "email", "textarea"):
        # Text value distribution
        distribution = (
            answers.filter(value_text__isnull=False)
            .values("value_text")
            .annotate(count=Count("id"))
            .order_by("-count")[:50]
        )
        result["distribution"] = {
            item["value_text"]: item["count"] for item in distribution
        }

    elif field_type == "checkbox":
        # JSON list distribution — flatten and count
        all_values = []
        for answer in answers.filter(value_json__isnull=False):
            if isinstance(answer.value_json, list):
                all_values.extend(answer.value_json)
        result["distribution"] = dict(Counter(all_values).most_common(50))

    elif field_type in ("number", "rating"):
        distribution = (
            answers.filter(value_number__isnull=False)
            .values("value_number")
            .annotate(count=Count("id"))
            .order_by("-count")[:50]
        )
        result["distribution"] = {
            str(item["value_number"]): item["count"] for item in distribution
        }

    elif field_type == "boolean":
        distribution = (
            answers.values("value_boolean")
            .annotate(count=Count("id"))
        )
        result["distribution"] = {
            str(item["value_boolean"]): item["count"] for item in distribution
        }

    return result
