from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # Customize the admin display for CustomUser
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('phone_number',)}),  # Add custom fields
    )

admin.site.register(CustomUser, CustomUserAdmin)
