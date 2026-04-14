from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsAnalystOrAbove
from apps.surveys.models import Survey
from apps.surveys.serializers import (
    SurveyCreateSerializer,
    SurveyDetailSerializer,
    SurveyListSerializer,
)
from apps.surveys.services.survey_builder import (
    archive_survey,
    duplicate_survey,
    publish_survey,
)


class SurveyListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SurveyCreateSerializer
        return SurveyListSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return Survey.objects.none()
        return Survey.objects.filter(
            organization=membership.organization
        ).prefetch_related("sections")

    def perform_create(self, serializer):
        membership = self.request.user.memberships.first()
        serializer.save(
            organization=membership.organization,
            created_by=self.request.user,
        )

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()


class SurveyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SurveyDetailSerializer
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return Survey.objects.none()
        return Survey.objects.filter(
            organization=membership.organization
        ).prefetch_related(
            "sections__fields__options",
            "visibility_rules__conditions",
            "field_dependencies",
        )

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return SurveyCreateSerializer
        return SurveyDetailSerializer

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        survey = self.get_object()
        survey.status = Survey.Status.ARCHIVED
        survey.save(update_fields=["status", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class SurveyPublishView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        membership = request.user.memberships.first()
        survey = Survey.objects.filter(
            id=pk, organization=membership.organization
        ).first()
        if not survey:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            version = publish_survey(survey)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"detail": "Survey published.", "version": version.version_number},
            status=status.HTTP_200_OK,
        )


class SurveyArchiveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        membership = request.user.memberships.first()
        survey = Survey.objects.filter(
            id=pk, organization=membership.organization
        ).first()
        if not survey:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            archive_survey(survey)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Survey archived."}, status=status.HTTP_200_OK)


class SurveyDuplicateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        membership = request.user.memberships.first()
        survey = Survey.objects.filter(
            id=pk, organization=membership.organization
        ).first()
        if not survey:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        new_survey = duplicate_survey(survey, request.user)
        serializer = SurveyDetailSerializer(new_survey)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
