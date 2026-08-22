"""Factories shared by tests and the seed_demo command."""
import datetime as dt

from django.contrib.auth import get_user_model

from rsm_thrive.models import StudentProfile


def make_student(username="ada", **overrides) -> StudentProfile:
    user = get_user_model().objects.create_user(username=username)
    fields = {
        "display_name": "Ada Lovelace",
        "program_start": dt.date(2026, 8, 1),
    }
    fields.update(overrides)
    return StudentProfile.objects.create(user=user, **fields)
