from django.urls import path

from apps.audit import views

urlpatterns = [
    path("audit-logs/", views.AuditLogListView.as_view(), name="audit-list"),
    path("audit-logs/<int:pk>/", views.AuditLogDetailView.as_view(), name="audit-detail"),
]
