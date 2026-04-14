"""Small cache helpers — keep keys centralized so invalidation is simple."""
from django.core.cache import cache

PUBLIC_SURVEY_TTL = 60 * 60          # 1 hour
ANALYTICS_SUMMARY_TTL = 60 * 5       # 5 minutes


def public_survey_key(survey_id) -> str:
    return f"public_survey:{survey_id}"


def analytics_summary_key(survey_id) -> str:
    return f"analytics_summary:{survey_id}"


def invalidate_survey_caches(survey_id) -> None:
    """Drop all caches tied to a specific survey. Call on publish/archive/new-submission."""
    cache.delete_many([
        public_survey_key(survey_id),
        analytics_summary_key(survey_id),
    ])
