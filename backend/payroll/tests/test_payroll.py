from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from payroll.models import PayExtra, StaffPay, extra_amount

PASSWORD = "Str0ng-pass-123"


def role(unit, code):
    return Role.objects.get(unit__code=unit, code=code)


class PayrollTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.boss = User.objects.create_superuser(username="boss", password=PASSWORD)
        self.production = User.objects.create_user(
            username="pm", password=PASSWORD, role=role("content", "production_manager")
        )
        self.hr = User.objects.create_user(username="hr", password=PASSWORD, role=role("content", "hr"))
        self.writer = User.objects.create_user(
            username="writer", first_name="Asha", password=PASSWORD, role=role("content", "content_writer")
        )
        self.dev = User.objects.create_user(
            username="dev", password=PASSWORD, role=role("web", "web_developer")
        )
        self.web_lead = User.objects.create_user(
            username="lead", password=PASSWORD, role=role("web", "team_lead")
        )

    def as_user(self, user):
        self.client.force_authenticate(user)

    def add_extra(self, **data):
        return self.client.post("/api/payroll/extras/", {"staff": self.writer.pk, "month": "2026-09", **data}, format="json")


class CalculationTests(TestCase):
    def test_rates(self):
        self.assertEqual(extra_amount(3000, 6000, 1000), Decimal("500.00"))
        self.assertEqual(extra_amount(6000, 6000, 1000), Decimal("1000.00"))
        self.assertEqual(extra_amount(4, 8, 1000), Decimal("500.00"))
        self.assertEqual(extra_amount(1000, 6000, 1000), Decimal("166.67"))


class PermissionTests(PayrollTestCase):
    def test_who_runs_payroll(self):
        for user in [self.boss, self.production, self.hr]:
            self.as_user(user)
            self.assertEqual(self.client.get("/api/payroll/staff/").status_code, 200, user.username)
        for user in [self.writer, self.dev, self.web_lead]:
            self.as_user(user)
            self.assertEqual(self.client.get("/api/payroll/staff/").status_code, 403, user.username)
            self.assertEqual(self.add_extra(kind="effort", amount="500").status_code, 403, user.username)

    def test_head_hr_does_not_run_content_payroll(self):
        head_hr = User.objects.create_user(username="chief", password=PASSWORD, role=Role.objects.get(code="head_hr"))
        self.as_user(head_hr)
        self.assertEqual(self.client.get("/api/payroll/staff/").status_code, 403)

    def test_only_content_staff_are_listed_and_payable(self):
        self.as_user(self.production)
        names = {row["username"] for row in self.client.get("/api/payroll/staff/").json()["staff"]}
        self.assertEqual(names, {"pm", "hr", "writer"})
        response = self.client.patch(f"/api/payroll/staff/{self.dev.pk}/", {"monthly_salary": "1"}, format="json")
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            "/api/payroll/extras/", {"staff": self.dev.pk, "month": "2026-09", "kind": "effort", "amount": "1"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_managers_cannot_change_their_own_pay(self):
        self.as_user(self.production)
        response = self.client.patch(f"/api/payroll/staff/{self.production.pk}/", {"monthly_salary": "99999"}, format="json")
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            "/api/payroll/extras/",
            {"staff": self.production.pk, "month": "2026-09", "kind": "performance", "amount": "5000"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        # HR can set the Production Manager's pay, and the Super Admin anyone's.
        self.as_user(self.hr)
        response = self.client.patch(f"/api/payroll/staff/{self.production.pk}/", {"monthly_salary": "60000"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_cannot_delete_own_extra(self):
        extra = PayExtra.objects.create(
            staff=self.hr, month="2026-09-01", kind="effort", amount=Decimal("100")
        )
        self.as_user(self.hr)
        self.assertEqual(self.client.delete(f"/api/payroll/extras/{extra.pk}/").status_code, 403)
        self.as_user(self.production)
        self.assertEqual(self.client.delete(f"/api/payroll/extras/{extra.pk}/").status_code, 204)


class PayTests(PayrollTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.production)

    def test_salary_and_rates_are_optional(self):
        response = self.client.patch(f"/api/payroll/staff/{self.writer.pk}/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        pay = StaffPay.objects.get(user=self.writer)
        self.assertIsNone(pay.monthly_salary)
        self.assertEqual((pay.words_per_rate, pay.words_rate_amount), (6000, Decimal("1000")))
        self.assertEqual((pay.hours_per_rate, pay.hours_rate_amount), (Decimal("8"), Decimal("1000")))

        response = self.client.patch(
            f"/api/payroll/staff/{self.writer.pk}/",
            {"monthly_salary": "25000", "daily_extra": True},
            format="json",
        )
        self.assertEqual(response.json()["pay"]["monthly_salary"], "25000.00")
        self.assertTrue(response.json()["pay"]["daily_extra"])

    def test_words_extra_uses_the_rate(self):
        response = self.add_extra(kind="words", quantity="3000")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["amount"], "500.00")
        self.assertEqual(response.json()["per_quantity"], "6000.00")

        response = self.add_extra(kind="words", quantity="3000", per_quantity="5000", per_amount="1500")
        self.assertEqual(response.json()["amount"], "900.00")

    def test_hours_extra_uses_the_staff_rate(self):
        StaffPay.objects.create(user=self.writer, hours_per_rate=Decimal("8"), hours_rate_amount=Decimal("1200"))
        response = self.add_extra(kind="hours", quantity="4")
        self.assertEqual(response.json()["amount"], "600.00")

    def test_client_cannot_override_calculated_amount(self):
        response = self.add_extra(kind="words", quantity="3000", amount="99999")
        self.assertEqual(response.json()["amount"], "500.00")

    def test_performance_and_effort_take_an_amount(self):
        self.assertEqual(self.add_extra(kind="performance", amount="2000").status_code, 201)
        self.assertEqual(self.add_extra(kind="effort").status_code, 400)
        self.assertEqual(self.add_extra(kind="words").status_code, 400)

    def test_daily_extras_and_monthly_total(self):
        self.client.patch(f"/api/payroll/staff/{self.writer.pk}/", {"monthly_salary": "20000"}, format="json")
        for day in ["2026-09-01", "2026-09-02"]:
            response = self.client.post(
                "/api/payroll/extras/",
                {"staff": self.writer.pk, "date": day, "kind": "words", "quantity": "6000"},
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.json())
            self.assertEqual(response.json()["month"], "2026-09")
        self.add_extra(kind="effort", amount="500")
        self.add_extra(kind="effort", amount="700", month="2026-10")

        rows = self.client.get("/api/payroll/staff/?month=2026-09").json()["staff"]
        row = next(r for r in rows if r["id"] == self.writer.pk)
        self.assertEqual(row["extras_by_kind"]["words"], "2000.00")
        self.assertEqual(row["extras_total"], "2500.00")
        self.assertEqual(row["total"], "22500.00")
        extras = self.client.get(f"/api/payroll/extras/?month=2026-09&staff={self.writer.pk}").json()
        self.assertEqual(len(extras), 3)

    def test_day_must_be_in_the_month(self):
        response = self.add_extra(kind="effort", amount="100", date="2026-10-03")
        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.json())

    def test_editing_an_extra_recalculates(self):
        extra_id = self.add_extra(kind="words", quantity="3000").json()["id"]
        response = self.client.patch(f"/api/payroll/extras/{extra_id}/", {"quantity": "9000"}, format="json")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["amount"], "1500.00")

    def test_bad_month(self):
        self.assertEqual(self.client.get("/api/payroll/staff/?month=sept").status_code, 400)


class DailyLogTests(PayrollTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.production)
        self.url = f"/api/payroll/staff/{self.writer.pk}/daily/?month=2026-09"

    def save(self, days):
        return self.client.put(self.url, {"days": days}, format="json")

    def test_each_day_is_priced_on_its_own(self):
        # 2 hours today, nothing tomorrow or the day after, 12 hours later on.
        response = self.save([
            {"date": "2026-09-01", "hours": "2"},
            {"date": "2026-09-02", "hours": None},
            {"date": "2026-09-03", "hours": 0},
            {"date": "2026-09-04", "hours": "12", "words": 3000},
        ])
        self.assertEqual(response.status_code, 200, response.json())
        days = {d["date"]: d for d in response.json()["days"]}
        self.assertEqual(set(days), {"2026-09-01", "2026-09-04"})
        self.assertEqual(days["2026-09-01"]["amount"], "250.00")
        self.assertEqual(days["2026-09-04"]["amount"], "2000.00")  # 12 h = 1,500 + 3,000 words = 500
        self.assertEqual(days["2026-09-04"]["words"], 3000)
        self.assertEqual(response.json()["staff"]["extras_total"], "2250.00")
        self.assertEqual(PayExtra.objects.filter(staff=self.writer).count(), 3)

    def test_saving_again_updates_and_clears_days(self):
        self.save([{"date": "2026-09-01", "hours": "2"}, {"date": "2026-09-04", "hours": "12"}])
        response = self.save([{"date": "2026-09-01", "hours": "3"}, {"date": "2026-09-04", "hours": None}])
        days = response.json()["days"]
        self.assertEqual([(d["date"], d["amount"]) for d in days], [("2026-09-01", "375.00")])

    def test_unchanged_days_keep_their_rate(self):
        self.save([{"date": "2026-09-01", "hours": "8"}])
        self.client.patch(f"/api/payroll/staff/{self.writer.pk}/", {"hours_rate_amount": "2000"}, format="json")
        response = self.save([{"date": "2026-09-01", "hours": "8"}, {"date": "2026-09-02", "hours": "8"}])
        amounts = [d["amount"] for d in response.json()["days"]]
        self.assertEqual(amounts, ["1000.00", "2000.00"])

    def test_other_extras_are_left_alone(self):
        self.add_extra(kind="performance", amount="1500")
        self.add_extra(kind="words", quantity="6000")  # a monthly, undated extra
        self.save([{"date": "2026-09-01", "hours": "2"}])
        self.save([])
        self.assertEqual(set(PayExtra.objects.filter(staff=self.writer).values_list("kind", flat=True)), {"performance", "words"})

    def test_day_limits(self):
        self.assertEqual(self.save([{"date": "2026-09-01", "hours": "25"}]).status_code, 400)
        self.assertEqual(self.save([{"date": "2026-10-01", "hours": "2"}]).status_code, 400)
        self.assertEqual(
            self.save([{"date": "2026-09-01", "hours": "2"}, {"date": "2026-09-01", "hours": "3"}]).status_code, 400
        )

    def test_single_extra_cannot_duplicate_a_logged_day(self):
        self.save([{"date": "2026-09-01", "hours": "2"}])
        response = self.add_extra(kind="hours", quantity="1", date="2026-09-01")
        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.json())

    def test_permissions(self):
        self.as_user(self.writer)
        self.assertEqual(self.save([]).status_code, 403)
        self.as_user(self.hr)
        own = self.client.put(f"/api/payroll/staff/{self.hr.pk}/daily/?month=2026-09", {"days": []}, format="json")
        self.assertEqual(own.status_code, 403)
        self.assertEqual(self.client.get(f"/api/payroll/staff/{self.dev.pk}/daily/").status_code, 404)
