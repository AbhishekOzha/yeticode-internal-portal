from django.contrib import admin

from .models import PayExtra, StaffPay


@admin.register(StaffPay)
class StaffPayAdmin(admin.ModelAdmin):
    list_display = ["user", "monthly_salary", "words_per_rate", "words_rate_amount", "hours_per_rate", "hours_rate_amount", "daily_extra"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email"]


@admin.register(PayExtra)
class PayExtraAdmin(admin.ModelAdmin):
    list_display = ["staff", "month", "date", "kind", "quantity", "amount"]
    list_filter = ["kind", "month"]
    search_fields = ["staff__username", "staff__first_name", "staff__last_name", "staff__email"]
