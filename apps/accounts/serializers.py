from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import Membership, Organization

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "user", "organization", "role", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    memberships = MembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "memberships"]
        read_only_fields = ["id"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    organization = serializers.UUIDField(write_only=True)
    role = serializers.ChoiceField(choices=Membership.Role.choices, write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "first_name", "last_name", "organization", "role"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        org_id = validated_data.pop("organization")
        role = validated_data.pop("role")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        Membership.objects.create(
            user=user,
            organization_id=org_id,
            role=role,
        )
        return user
