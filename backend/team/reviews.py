"""Colleague reviews for the Academic Content Writing team.

Everyone in the team can rate and comment on everyone else in it (writers,
supervisors, the Production Manager, Sales Manager, HR, …) once a month, and
change or withdraw their own review. Reviews are read by Super Admins and by
the unit's HR and Production Manager, never by the person reviewed, so people
can be candid; nobody can read the reviews written about themselves.
"""

import datetime
from collections import defaultdict

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Review
from .views import IsTeamMember, in_team, person, team_members

READER_CAPABILITIES = ["manage_employee_records", "manage_unit_users"]


def can_read_reviews(user):
    if user.is_superuser:
        return True
    return in_team(user) and any(user.has_perm(f"accounts.{code}") for code in READER_CAPABILITIES)


class CanReadReviews(BasePermission):
    message = "Only Super Admins, HR and the Production Manager can read reviews."

    def has_permission(self, request, view):
        return can_read_reviews(request.user)


def parse_month(value):
    if not value:
        return timezone.localdate().replace(day=1)
    try:
        return datetime.datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        raise ValidationError({"month": "Use the form YYYY-MM, e.g. 2026-09."})


def review_data(review):
    return {
        "id": review.pk,
        "subject": review.subject_id,
        "month": review.month.strftime("%Y-%m"),
        "rating": review.rating,
        "comment": review.comment,
        "updated_at": review.updated_at.isoformat(),
    }


class ReviewInputSerializer(serializers.Serializer):
    subject = serializers.IntegerField()
    month = serializers.CharField(required=False, allow_blank=True)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class ReviewPeopleView(APIView):
    """Your colleagues, each with the review you wrote about them for ?month=YYYY-MM (if any)."""

    permission_classes = [IsTeamMember]

    def get(self, request):
        month = parse_month(request.query_params.get("month"))
        mine = {r.subject_id: r for r in Review.objects.filter(author=request.user, month=month)}
        people = team_members().exclude(pk=request.user.pk)
        return Response({
            "month": month.strftime("%Y-%m"),
            "people": [
                {**person(p), "my_review": review_data(mine[p.pk]) if p.pk in mine else None}
                for p in people
            ],
        })


class ReviewWriteView(APIView):
    """POST writes (or rewrites) your review of a colleague for a month."""

    permission_classes = [IsTeamMember]

    def post(self, request):
        serializer = ReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["subject"] == request.user.pk:
            raise ValidationError({"subject": "You can't review yourself."})
        subject = team_members().filter(pk=data["subject"]).first()
        if subject is None:
            raise ValidationError({"subject": "You can only review people in your own team."})
        month = parse_month(data.get("month"))
        if month > timezone.localdate().replace(day=1):
            raise ValidationError({"month": "You can't review a month that hasn't started."})
        review, created = Review.objects.update_or_create(
            author=request.user, subject=subject, month=month,
            defaults={"rating": data["rating"], "comment": data.get("comment", "").strip()},
        )
        return Response(review_data(review), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ReviewDeleteView(APIView):
    permission_classes = [IsTeamMember]

    def delete(self, request, pk):
        review = get_object_or_404(Review, pk=pk)
        if review.author_id != request.user.pk:
            raise PermissionDenied("You can only withdraw your own reviews.")
        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReviewSummaryView(APIView):
    """Everyone's reviews for ?month=YYYY-MM, with the average rating. Not your own."""

    permission_classes = [CanReadReviews]

    def get(self, request):
        month = parse_month(request.query_params.get("month"))
        members = list(team_members())
        reviews = (
            Review.objects.filter(month=month, subject__in=members)
            .exclude(subject=request.user)
            .select_related("author__role")
        )
        by_subject = defaultdict(list)
        for review in reviews:
            by_subject[review.subject_id].append(review)
        rows = []
        for member in members:
            if member.pk == request.user.pk:
                continue  # Nobody reads the reviews about themselves.
            received = by_subject[member.pk]
            rows.append({
                **person(member),
                "count": len(received),
                "average": round(sum(r.rating for r in received) / len(received), 2) if received else None,
                "reviews": [{**review_data(r), "author": person(r.author)} for r in received],
            })
        return Response({"month": month.strftime("%Y-%m"), "people": rows})
