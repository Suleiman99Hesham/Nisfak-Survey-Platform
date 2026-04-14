from django.core.cache import cache
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.cache import ANALYTICS_SUMMARY_TTL, analytics_summary_key

from apps.accounts.permissions import IsAdmin, IsAnalystOrAbove, IsDataViewerOrAbove
from apps.analytics.models import ReportExport, SurveyInvitation
from apps.analytics.selectors.analytics_selectors import (
    get_field_analytics,
    get_survey_summary,
)
from apps.analytics.serializers import (
    InvitationRequestSerializer,
    ReportExportSerializer,
    SurveyInvitationSerializer,
)
from apps.audit.services import log_action
from apps.surveys.models import Survey


class SurveyAnalyticsSummaryView(APIView):
    """GET /surveys/<id>/analytics/summary/ — Aggregated survey results."""
    permission_classes = [IsAuthenticated, IsDataViewerOrAbove]

    def get(self, request, survey_pk):
        membership = request.user.memberships.first()
        try:
            survey = Survey.objects.get(
                id=survey_pk, organization=membership.organization
            )
        except Survey.DoesNotExist:
            return Response(
                {"detail": "Survey not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        cache_key = analytics_summary_key(survey.id)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        summary = get_survey_summary(survey)
        cache.set(cache_key, summary, ANALYTICS_SUMMARY_TTL)
        return Response(summary)


class FieldAnalyticsView(APIView):
    """GET /surveys/<id>/analytics/fields/<field_id>/ — Per-field breakdown."""
    permission_classes = [IsAuthenticated, IsDataViewerOrAbove]

    def get(self, request, survey_pk, field_pk):
        membership = request.user.memberships.first()
        try:
            survey = Survey.objects.get(
                id=survey_pk, organization=membership.organization
            )
        except Survey.DoesNotExist:
            return Response(
                {"detail": "Survey not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        analytics = get_field_analytics(survey, field_pk)
        return Response(analytics)


class ExportRequestView(APIView):
    """POST /surveys/<id>/exports/ — Request async export."""
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def post(self, request, survey_pk):
        membership = request.user.memberships.first()
        try:
            survey = Survey.objects.get(
                id=survey_pk, organization=membership.organization
            )
        except Survey.DoesNotExist:
            return Response(
                {"detail": "Survey not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        export_format = request.data.get("format", "csv")
        if export_format not in ("csv", "xlsx", "pdf"):
            return Response(
                {"detail": "Invalid format. Choose csv, xlsx, or pdf."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        export = ReportExport.objects.create(
            survey=survey,
            requested_by=request.user,
            export_format=export_format,
            filters=request.data.get("filters", {}),
        )

        # Trigger async export task
        from apps.analytics.tasks import generate_export
        generate_export.delay(str(export.id))

        serializer = ReportExportSerializer(export)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InvitationBatchView(APIView):
    """POST /surveys/<id>/invitations/ — Send survey invitations in bulk (async)."""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, survey_pk):
        import secrets
        import uuid as _uuid

        from apps.analytics.tasks import send_invitation_batch

        membership = request.user.memberships.first()
        try:
            survey = Survey.objects.get(
                id=survey_pk,
                organization=membership.organization,
                status=Survey.Status.PUBLISHED,
            )
        except Survey.DoesNotExist:
            return Response(
                {"detail": "Published survey not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = InvitationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emails = list({e.lower() for e in serializer.validated_data["emails"]})

        batch_id = _uuid.uuid4()
        invitations = [
            SurveyInvitation(
                survey=survey,
                batch_id=batch_id,
                email=email,
                token=secrets.token_hex(32),
                invited_by=request.user,
            )
            for email in emails
        ]
        SurveyInvitation.objects.bulk_create(invitations)

        send_invitation_batch.delay(str(batch_id))

        log_action(
            actor=request.user,
            action="invitation.batch.send",
            entity_type="survey",
            entity_id=str(survey.id),
            organization=survey.organization,
            metadata={"batch_id": str(batch_id), "count": len(emails)},
            request=request,
        )

        return Response(
            {"batch_id": str(batch_id), "queued": len(emails)},
            status=status.HTTP_202_ACCEPTED,
        )


class InvitationListView(generics.ListAPIView):
    """GET /surveys/<id>/invitations/ — List invitations for a survey."""
    serializer_class = SurveyInvitationSerializer
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return SurveyInvitation.objects.none()
        return SurveyInvitation.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        )


class ExportDetailView(generics.RetrieveAPIView):
    """GET /exports/<id>/ — Check export status / download."""
    serializer_class = ReportExportSerializer
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return ReportExport.objects.none()
        return ReportExport.objects.filter(
            survey__organization=membership.organization
        )
