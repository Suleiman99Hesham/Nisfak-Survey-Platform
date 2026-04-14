from django.core.cache import cache
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAnalystOrAbove
from apps.common.cache import PUBLIC_SURVEY_TTL, public_survey_key
from apps.responses.models import SurveySubmission
from apps.responses.serializers import (
    AnswerInputSerializer,
    SurveySubmissionListSerializer,
    SurveySubmissionSerializer,
)
from apps.responses.services.submission_service import (
    save_answers,
    start_submission,
    submit_response,
)
from apps.surveys.models import Survey
from apps.surveys.serializers import SurveyDetailSerializer


class PublicSurveyView(APIView):
    """GET /public/surveys/<id>/ — Get a published survey for responding.

    Cached in Redis for 1h keyed by survey id. Invalidated on publish/archive.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        cache_key = public_survey_key(pk)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        try:
            survey = Survey.objects.prefetch_related(
                "sections__fields__options",
                "visibility_rules__conditions",
                "field_dependencies",
            ).get(id=pk, status=Survey.Status.PUBLISHED)
        except Survey.DoesNotExist:
            return Response(
                {"detail": "Survey not found or not published."},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = SurveyDetailSerializer(survey).data
        cache.set(cache_key, data, PUBLIC_SURVEY_TTL)
        return Response(data)


class StartSubmissionView(APIView):
    """POST /public/surveys/<id>/start/ — Start a new submission."""
    permission_classes = [AllowAny]

    def post(self, request, pk):
        try:
            survey = Survey.objects.get(id=pk, status=Survey.Status.PUBLISHED)
        except Survey.DoesNotExist:
            return Response(
                {"detail": "Survey not found or not published."},
                status=status.HTTP_404_NOT_FOUND,
            )

        respondent = request.user if request.user.is_authenticated else None
        ip = request.META.get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT", "")

        try:
            submission = start_submission(survey, respondent, ip, ua)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SurveySubmissionSerializer(submission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SaveAnswersView(APIView):
    """POST /public/responses/<id>/answers/ — Auto-save answers."""
    permission_classes = [AllowAny]

    def post(self, request, pk):
        submission = self._get_submission(request, pk)
        if not submission:
            return Response(
                {"detail": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AnswerInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        try:
            save_answers(submission, serializer.validated_data)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Answers saved.", "completion": submission.completion_percentage},
            status=status.HTTP_200_OK,
        )

    def _get_submission(self, request, pk):
        qs = SurveySubmission.objects.filter(id=pk, status="in_progress")
        if request.user.is_authenticated:
            return qs.filter(respondent=request.user).first()
        # Anonymous — require resume_token in header
        token = request.headers.get("X-Resume-Token")
        if token:
            return qs.filter(resume_token=token).first()
        return None


class SaveDraftView(APIView):
    """POST /public/responses/<id>/save-draft/ — Explicit draft save.

    Body is an optional list of answers; if omitted, acts as a heartbeat that
    just bumps ``last_saved_at`` on the submission.
    """
    permission_classes = [AllowAny]

    def post(self, request, pk):
        submission = SaveAnswersView()._get_submission(request, pk)
        if not submission:
            return Response(
                {"detail": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.data:
            serializer = AnswerInputSerializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            try:
                save_answers(submission, serializer.validated_data)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            submission.save(update_fields=["last_saved_at"])

        return Response(
            {"detail": "Draft saved.", "completion": submission.completion_percentage},
            status=status.HTTP_200_OK,
        )


class SubmitResponseView(APIView):
    """POST /public/responses/<id>/submit/ — Final submission with full validation."""
    permission_classes = [AllowAny]

    def post(self, request, pk):
        submission = self._get_submission(request, pk)
        if not submission:
            return Response(
                {"detail": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        success, errors = submit_response(submission)
        if not success:
            return Response(
                {"detail": "Validation failed.", "errors": errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SurveySubmissionSerializer(submission)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_submission(self, request, pk):
        qs = SurveySubmission.objects.filter(id=pk, status="in_progress")
        if request.user.is_authenticated:
            return qs.filter(respondent=request.user).first()
        token = request.headers.get("X-Resume-Token")
        if token:
            return qs.filter(resume_token=token).first()
        return None


class ResumeSubmissionView(APIView):
    """GET /public/responses/resume/<token>/ — Resume a draft submission by token."""
    permission_classes = [AllowAny]

    def get(self, request, token):
        submission = SurveySubmission.objects.filter(
            resume_token=token, status="in_progress"
        ).first()
        if not submission:
            return Response(
                {"detail": "Submission not found or already completed."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SurveySubmissionSerializer(
            submission, context={"request": request}
        )
        return Response(serializer.data)


class SubmissionCurrentView(APIView):
    """GET /public/responses/<id>/current/ — Get current response state."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        submission = SurveySubmission.objects.filter(id=pk).first()
        if not submission:
            return Response(
                {"detail": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SurveySubmissionSerializer(
            submission, context={"request": request}
        )
        return Response(serializer.data)


class SubmissionDetailView(generics.RetrieveAPIView):
    """GET /submissions/<id>/ — Admin/Analyst view of a submission."""
    serializer_class = SurveySubmissionSerializer
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return SurveySubmission.objects.none()
        return SurveySubmission.objects.filter(
            survey__organization=membership.organization
        ).prefetch_related("answers")


class SubmissionListView(generics.ListAPIView):
    """GET /surveys/<id>/submissions/ — List submissions for a survey."""
    serializer_class = SurveySubmissionListSerializer
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return SurveySubmission.objects.none()
        return SurveySubmission.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        )
