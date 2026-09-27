from django.contrib import admin

from .models import OfficeHours

# Chat messages are deliberately not in the admin: conversations stay within the team.


@admin.register(OfficeHours)
class OfficeHoursAdmin(admin.ModelAdmin):
    list_display = ["user", "start_time", "end_time", "work_days", "reminders"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email"]
