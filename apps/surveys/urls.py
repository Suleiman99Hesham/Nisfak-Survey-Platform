from django.urls import path

from apps.surveys.views import (
    FieldDependencyDetailView,
    FieldDependencyListCreateView,
    FieldDetailView,
    FieldListCreateView,
    FieldOptionDetailView,
    FieldOptionListCreateView,
    FieldReorderView,
    SectionDetailView,
    SectionListCreateView,
    SectionReorderView,
    SurveyArchiveView,
    SurveyDetailView,
    SurveyDuplicateView,
    SurveyListCreateView,
    SurveyPublishView,
    VisibilityRuleDetailView,
    VisibilityRuleListCreateView,
)

urlpatterns = [
    # Surveys
    path("surveys/", SurveyListCreateView.as_view(), name="survey-list"),
    path("surveys/<uuid:pk>/", SurveyDetailView.as_view(), name="survey-detail"),
    path("surveys/<uuid:pk>/publish/", SurveyPublishView.as_view(), name="survey-publish"),
    path("surveys/<uuid:pk>/archive/", SurveyArchiveView.as_view(), name="survey-archive"),
    path("surveys/<uuid:pk>/duplicate/", SurveyDuplicateView.as_view(), name="survey-duplicate"),
    # Sections
    path("surveys/<uuid:survey_pk>/sections/", SectionListCreateView.as_view(), name="section-list"),
    path("surveys/<uuid:survey_pk>/sections/<uuid:pk>/", SectionDetailView.as_view(), name="section-detail"),
    path("surveys/<uuid:survey_pk>/sections/reorder/", SectionReorderView.as_view(), name="section-reorder"),
    # Fields
    path("sections/<uuid:section_pk>/fields/", FieldListCreateView.as_view(), name="field-list"),
    path("sections/<uuid:section_pk>/fields/<uuid:pk>/", FieldDetailView.as_view(), name="field-detail"),
    path("sections/<uuid:section_pk>/fields/reorder/", FieldReorderView.as_view(), name="field-reorder"),
    # Field Options
    path("fields/<uuid:field_pk>/options/", FieldOptionListCreateView.as_view(), name="option-list"),
    path("fields/<uuid:field_pk>/options/<uuid:pk>/", FieldOptionDetailView.as_view(), name="option-detail"),
    # Visibility Rules
    path("surveys/<uuid:survey_pk>/rules/", VisibilityRuleListCreateView.as_view(), name="rule-list"),
    path("surveys/<uuid:survey_pk>/rules/<uuid:pk>/", VisibilityRuleDetailView.as_view(), name="rule-detail"),
    # Field Dependencies
    path("surveys/<uuid:survey_pk>/dependencies/", FieldDependencyListCreateView.as_view(), name="dependency-list"),
    path("surveys/<uuid:survey_pk>/dependencies/<uuid:pk>/", FieldDependencyDetailView.as_view(), name="dependency-detail"),
]
