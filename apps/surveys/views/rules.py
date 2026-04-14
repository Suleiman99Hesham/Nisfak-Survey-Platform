from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdmin, IsAnalystOrAbove
from apps.surveys.models import FieldDependency, Survey, VisibilityRule
from apps.surveys.serializers import (
    FieldDependencyCreateSerializer,
    FieldDependencySerializer,
    VisibilityRuleCreateSerializer,
    VisibilityRuleSerializer,
)


class VisibilityRuleListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VisibilityRuleCreateSerializer
        return VisibilityRuleSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return VisibilityRule.objects.none()
        return VisibilityRule.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        ).prefetch_related("conditions")

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


class VisibilityRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return VisibilityRuleCreateSerializer
        return VisibilityRuleSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return VisibilityRule.objects.none()
        return VisibilityRule.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        ).prefetch_related("conditions")


class FieldDependencyListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FieldDependencyCreateSerializer
        return FieldDependencySerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return FieldDependency.objects.none()
        return FieldDependency.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        )

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


class FieldDependencyDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return FieldDependencyCreateSerializer
        return FieldDependencySerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return FieldDependency.objects.none()
        return FieldDependency.objects.filter(
            survey_id=self.kwargs["survey_pk"],
            survey__organization=membership.organization,
        )
