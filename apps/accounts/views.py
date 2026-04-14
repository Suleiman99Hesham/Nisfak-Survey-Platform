from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Membership
from apps.accounts.permissions import IsAdmin
from apps.accounts.serializers import (
    MembershipSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()


class UserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return User.objects.none()
        org_user_ids = Membership.objects.filter(
            organization=membership.organization
        ).values_list("user_id", flat=True)
        return User.objects.filter(id__in=org_user_ids).prefetch_related("memberships")


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        membership = self.request.user.memberships.first()
        if not membership:
            return User.objects.none()
        org_user_ids = Membership.objects.filter(
            organization=membership.organization
        ).values_list("user_id", flat=True)
        return User.objects.filter(id__in=org_user_ids).prefetch_related("memberships")

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
