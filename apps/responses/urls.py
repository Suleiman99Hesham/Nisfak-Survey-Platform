from django.urls import path

from apps.responses import views

urlpatterns = [
    # Public respondent-facing endpoints
    path("public/surveys/<uuid:pk>/", views.PublicSurveyView.as_view(), name="public-survey"),
    path("public/surveys/<uuid:pk>/start/", views.StartSubmissionView.as_view(), name="start-submission"),
    path("public/responses/<uuid:pk>/answers/", views.SaveAnswersView.as_view(), name="save-answers"),
    path("public/responses/<uuid:pk>/save-draft/", views.SaveDraftView.as_view(), name="save-draft"),
    path("public/responses/<uuid:pk>/submit/", views.SubmitResponseView.as_view(), name="submit-response"),
    path("public/responses/<uuid:pk>/current/", views.SubmissionCurrentView.as_view(), name="submission-current"),
    path("public/responses/resume/<str:token>/", views.ResumeSubmissionView.as_view(), name="resume-submission"),
    # Admin/Analyst endpoints
    path("submissions/<uuid:pk>/", views.SubmissionDetailView.as_view(), name="submission-detail"),
    path("surveys/<uuid:survey_pk>/submissions/", views.SubmissionListView.as_view(), name="submission-list"),
]
