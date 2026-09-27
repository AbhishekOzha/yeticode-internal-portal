from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("payroll/extras", views.PayExtraViewSet, basename="payroll-extras")

urlpatterns = [
    path("payroll/staff/", views.StaffPayListView.as_view(), name="payroll-staff"),
    path("payroll/staff/<uuid:pk>/", views.StaffPayDetailView.as_view(), name="payroll-staff-detail"),
    path("payroll/staff/<uuid:pk>/payslip/", views.PayslipView.as_view(), name="payroll-payslip"),
    path("payroll/staff/<uuid:pk>/daily/", views.DailyLogView.as_view(), name="payroll-daily"),
] + router.urls
