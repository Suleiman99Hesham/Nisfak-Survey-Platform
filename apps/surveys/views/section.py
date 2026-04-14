from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsAnalystOrAbove
from apps.surveys.models import Survey, SurveySection
from apps.surveys.serializers import SurveySectionCreateSerializer, SurveySectionSerializer


class SectionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SurveySectionCreateSerializer
        return SurveySectionSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return SurveySection.objects.none()
        return SurveySection.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        ).prefetch_related("fields__options")

    def perform_create(self, serializer):
        membership = self.request.user.memberships.first()
        survey = Survey.objects.get(
            id=self.kwargs["survey_pk"],
            organization=membership.organization,
        )
        serializer.save(survey=survey)

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()


class SectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return SurveySectionCreateSerializer
        return SurveySectionSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return SurveySection.objects.none()
        return SurveySection.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        ).prefetch_related("fields__options")

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()


class SectionReorderView(APIView):
    """Reorder sections within a survey. Expects: {"order": ["uuid1", "uuid2", ...]}"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, survey_pk):
        membership = request.user.memberships.first()
        section_ids = request.data.get("order", [])
        if not section_ids:
            return Response(
                {"detail": "Provide 'order' as a list of section IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sections = SurveySection.objects.filter(
            survey_id=survey_pk,
            survey__organization=membership.organization,
        )
        section_map = {str(s.id): s for s in sections}

        for i, section_id in enumerate(section_ids):
            section = section_map.get(section_id)
            if section:
                section.order = i
        SurveySection.objects.bulk_update(section_map.values(), ["order"])

        return Response({"detail": "Sections reordered."}, status=status.HTTP_200_OK)
