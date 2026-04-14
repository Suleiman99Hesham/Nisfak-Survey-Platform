from django.urls import path

from apps.analytics import views

urlpatterns = [
    path("surveys/<uuid:survey_pk>/analytics/summary/", views.SurveyAnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("surveys/<uuid:survey_pk>/analytics/fields/<uuid:field_pk>/", views.FieldAnalyticsView.as_view(), name="field-analytics"),
    path("surveys/<uuid:survey_pk>/exports/", views.ExportRequestView.as_view(), name="export-request"),
    path("exports/<uuid:pk>/", views.ExportDetailView.as_view(), name="export-detail"),
    path("surveys/<uuid:survey_pk>/invitations/", views.InvitationBatchView.as_view(), name="invitation-batch"),
    path("surveys/<uuid:survey_pk>/invitations/list/", views.InvitationListView.as_view(), name="invitation-list"),
]
