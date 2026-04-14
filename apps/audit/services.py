from apps.audit.models import AuditLog


def log_action(
    actor,
    action: str,
    entity_type: str,
    entity_id: str,
    request=None,
    changes: dict = None,
    metadata: dict = None,
    organization=None,
):
    """
    Create an audit log entry.

    Args:
        actor: User instance (or None for system actions)
        action: e.g. "survey.create", "survey.publish", "response.submit"
        entity_type: e.g. "survey", "submission", "export"
        entity_id: UUID string of the affected entity
        request: HTTP request (for IP and user agent)
        changes: dict of {"field": {"old": ..., "new": ...}}
        metadata: extra context dict
        organization: explicit Organization (overrides actor's membership lookup).
            Required for actions taken by anonymous or cross-org actors — e.g.
            a public respondent submitting into an organization's survey.
    """
    ip_address = None
    user_agent = ""

    if request:
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")

    if organization is None and actor and hasattr(actor, "memberships"):
        membership = actor.memberships.first()
        if membership:
            organization = membership.organization

    AuditLog.objects.create(
        actor=actor if actor and actor.is_authenticated else None,
        organization=organization,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {},
    )
