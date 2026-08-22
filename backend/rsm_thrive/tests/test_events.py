import pytest
from django.utils import timezone

from rsm_thrive.testing import make_event, make_student

pytestmark = pytest.mark.django_db


def test_events_future_filter_sort_and_relevance(client):
    profile = make_student(goal="Data Scientist")
    now = timezone.now()
    day = timezone.timedelta(days=1)
    make_event(id="past", start=now - 3 * day)                      # gone
    make_event(id="running", start=now - 2 * day, end=now + day)    # kept: end >= now
    make_event(id="soon", start=now + day,
               goal_tags=["data scientist", "ml engineer"])          # relevant
    make_event(id="later", start=now + 5 * day)

    client.force_login(profile.user)
    body = client.get("/api/thrive/events").json()

    assert [e["id"] for e in body] == ["running", "soon", "later"]  # start asc
    by_id = {e["id"]: e for e in body}
    assert by_id["soon"]["relevantToGoal"] is True
    assert by_id["later"]["relevantToGoal"] is False
    assert "end" in by_id["running"] and "end" not in by_id["soon"]
