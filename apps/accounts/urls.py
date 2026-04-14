from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts import views

urlpatterns = [
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("users/", views.UserListCreateView.as_view(), name="user-list"),
    path("users/me/", views.CurrentUserView.as_view(), name="current-user"),
    path("users/<uuid:pk>/", views.UserDetailView.as_view(), name="user-detail"),
]
