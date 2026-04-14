from rest_framework.permissions import BasePermission

from apps.accounts.models import Membership


def _get_membership(request):
    """Get the user's membership for the current organization context."""
    if not request.user.is_authenticated:
        return None
    org_id = request.headers.get("X-Organization-Id") or request.query_params.get("org")
    if not org_id:
        return request.user.memberships.first()
    return request.user.memberships.filter(organization_id=org_id).first()


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        membership = _get_membership(request)
        return membership is not None and membership.role == Membership.Role.ADMIN


class IsAnalystOrAbove(BasePermission):
    def has_permission(self, request, view):
        membership = _get_membership(request)
        return membership is not None and membership.role in (
            Membership.Role.ADMIN,
            Membership.Role.ANALYST,
        )


class IsDataViewerOrAbove(BasePermission):
    def has_permission(self, request, view):
        membership = _get_membership(request)
        return membership is not None and membership.role in (
            Membership.Role.ADMIN,
            Membership.Role.ANALYST,
            Membership.Role.DATA_VIEWER,
        )
