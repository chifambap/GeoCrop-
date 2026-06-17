from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Field App', {'fields': ('role', 'organisation', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Field App', {'fields': ('role', 'organisation', 'phone')}),
    )
    list_display  = ['username', 'email', 'role', 'organisation', 'is_active']
    list_filter   = ['role', 'is_active']
    search_fields = ['username', 'email', 'organisation']
