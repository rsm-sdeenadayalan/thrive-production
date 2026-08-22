import pytest
from django.db import IntegrityError, transaction

from rsm_thrive.models import Appointment
from rsm_thrive.testing import make_advisor, make_slot, make_student

pytestmark = pytest.mark.django_db


def test_only_one_confirmed_appointment_per_slot():
    slot = make_slot(make_advisor())
    a = make_student(username="a")
    b = make_student(username="b")
    Appointment.objects.create(slot=slot, student=a.user, reason="r1")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Appointment.objects.create(slot=slot, student=b.user, reason="r2")


def test_cancelled_appointment_frees_the_slot():
    slot = make_slot(make_advisor())
    a = make_student(username="a")
    b = make_student(username="b")
    first = Appointment.objects.create(slot=slot, student=a.user, reason="r1")
    first.status = "cancelled"
    first.save()
    second = Appointment.objects.create(slot=slot, student=b.user, reason="r2")
    assert second.pk != first.pk


def test_student_factory_has_email():
    profile = make_student(username="ada")
    assert profile.user.email == "ada@ucsd.edu"
