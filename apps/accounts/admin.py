from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import Membership, Organization, User


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [MembershipInline]


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role", "created_at"]
    list_filter = ["role", "organization"]
