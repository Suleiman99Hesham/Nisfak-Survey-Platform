from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsAnalystOrAbove
from apps.surveys.models import FieldOption, SurveyField, SurveySection
from apps.surveys.serializers import (
    FieldOptionSerializer,
    SurveyFieldCreateSerializer,
    SurveyFieldSerializer,
)


class FieldListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return SurveyFieldCreateSerializer
        return SurveyFieldSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return SurveyField.objects.none()
        return SurveyField.objects.filter(
            section_id=self.kwargs["section_pk"],
            section__survey__organization=membership.organization,
        ).prefetch_related("options")

    def perform_create(self, serializer):
        membership = self.request.user.memberships.first()
        section = SurveySection.objects.get(
            id=self.kwargs["section_pk"],
            survey__organization=membership.organization,
        )
        serializer.save(section=section)

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()


class FieldDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return SurveyFieldCreateSerializer
        return SurveyFieldSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return SurveyField.objects.none()
        return SurveyField.objects.filter(
            section_id=self.kwargs["section_pk"],
            section__survey__organization=membership.organization,
        ).prefetch_related("options")

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()


class FieldReorderView(APIView):
    """Reorder fields within a section. Expects: {"order": ["uuid1", "uuid2", ...]}"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, section_pk):
        membership = request.user.memberships.first()
        field_ids = request.data.get("order", [])
        if not field_ids:
            return Response(
                {"detail": "Provide 'order' as a list of field IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fields = SurveyField.objects.filter(
            section_id=section_pk,
            section__survey__organization=membership.organization,
        )
        field_map = {str(f.id): f for f in fields}

        for i, field_id in enumerate(field_ids):
            field = field_map.get(field_id)
            if field:
                field.order = i
        SurveyField.objects.bulk_update(field_map.values(), ["order"])

        return Response({"detail": "Fields reordered."}, status=status.HTTP_200_OK)


class FieldOptionListCreateView(generics.ListCreateAPIView):
    serializer_class = FieldOptionSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return FieldOption.objects.none()
        return FieldOption.objects.filter(
            field_id=self.kwargs["field_pk"],
            field__section__survey__organization=membership.organization,
        )

    def perform_create(self, serializer):
        membership = self.request.user.memberships.first()
        field = SurveyField.objects.get(
            id=self.kwargs["field_pk"],
            section__survey__organization=membership.organization,
        )
        serializer.save(field=field)


class FieldOptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FieldOptionSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return FieldOption.objects.none()
        return FieldOption.objects.filter(
            field_id=self.kwargs["field_pk"],
            field__section__survey__organization=membership.organization,
        )
