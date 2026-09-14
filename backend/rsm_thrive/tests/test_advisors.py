import datetime as dt
from unittest.mock import patch

import pytest
from django.utils import timezone

from rsm_thrive.models import Appointment
from rsm_thrive.services import graph
from rsm_thrive.testing import (
    make_advisor,
    make_calendar_connection,
    make_slot,
    make_student,
)

pytestmark = pytest.mark.django_db


def test_advisors_shape_and_sort(client):
    profile = make_student()
    make_advisor(id="a2", name="Zoe", service="career", blurb="Careers")
    make_advisor(id="a1", name="Ana", service="advising",
                 avatar_url="https://rady.ucsd.edu/a.png")
    client.force_login(profile.user)
    body = client.get("/api/thrive/advisors").json()
    assert [a["id"] for a in body] == ["a1", "a2"]  # advising < career
    assert body[0]["avatar"] == "https://rady.ucsd.edu/a.png"
    assert "blurb" not in body[0]
    assert body[1]["blurb"] == "Careers"
    assert "avatar" not in body[1]
    assert "email" not in body[0] and "email" not in body[1]  # internal field


def test_slots_availability_and_sort(client):
    profile = make_student()
    other = make_student(username="other")
    adv = make_advisor(id="a1")
    base = timezone.now() + dt.timedelta(days=3)
    s2 = make_slot(adv, start=base + dt.timedelta(hours=1))
    s1 = make_slot(adv, start=base)
    Appointment.objects.create(slot=s1, student=other.user, reason="x")

    client.force_login(profile.user)
    body = client.get(f"/api/thrive/advisors/{adv.id}/slots").json()
    assert [s["id"] for s in body] == [s1.id, s2.id]       # start asc
    assert body[0]["available"] is False                    # taken, still listed
    assert body[1]["available"] is True
    assert body[0]["advisorId"] == "a1"
    assert body[0]["mode"] == "zoom"


def test_slots_unknown_advisor_404(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/advisors/nope/slots")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "unknown_advisor"


def test_slots_unaffected_when_advisor_not_connected(client):
    profile = make_student()
    adv = make_advisor(id="a1")
    make_slot(adv)
    client.force_login(profile.user)
    with patch("rsm_thrive.services.graph.get_busy_periods") as mocked:
        body = client.get(f"/api/thrive/advisors/{adv.id}/slots").json()
    mocked.assert_not_called()
    assert body[0]["available"] is True


def test_slots_filtered_by_graph_busy_periods_when_connected(client):
    profile = make_student()
    adv = make_advisor(id="a1")
    make_calendar_connection(adv)
    base = timezone.now() + dt.timedelta(days=3)
    busy_slot = make_slot(adv, start=base)
    free_slot = make_slot(adv, start=base + dt.timedelta(hours=2))
    client.force_login(profile.user)
    with patch("rsm_thrive.services.graph.get_busy_periods",
              return_value=[(busy_slot.start, busy_slot.end)]):
        body = client.get(f"/api/thrive/advisors/{adv.id}/slots").json()
    by_id = {s["id"]: s["available"] for s in body}
    assert by_id[busy_slot.id] is False
    assert by_id[free_slot.id] is True


def test_slots_graph_failure_degrades_to_unfiltered(client):
    profile = make_student()
    adv = make_advisor(id="a1")
    make_calendar_connection(adv)
    slot = make_slot(adv)
    client.force_login(profile.user)
    with patch("rsm_thrive.services.graph.get_busy_periods",
              side_effect=graph.GraphError("down")):
        resp = client.get(f"/api/thrive/advisors/{adv.id}/slots")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == slot.id
    assert resp.json()[0]["available"] is True
