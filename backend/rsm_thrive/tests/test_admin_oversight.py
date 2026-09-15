"""Tests for the faculty layer: curriculum read access and answer review."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from rsm_thrive import testing


def _client_for(group_name=None, username="ov-user"):
    user = get_user_model().objects.create_user(username, is_staff=True)
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    client = Client()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_faculty_can_view_courses_but_not_add():
    testing.make_course()
    client, _ = _client_for("THRIVE Faculty", "fac-view")
    assert client.get(reverse("admin:rsm_thrive_course_changelist")).status_code == 200
    assert client.get(reverse("admin:rsm_thrive_course_add")).status_code == 403


@pytest.mark.django_db
def test_admin_can_add_course():
    client, _ = _client_for("THRIVE Admin", "adm-add")
    assert client.get(reverse("admin:rsm_thrive_course_add")).status_code == 200


@pytest.mark.django_db
def test_answer_review_visible_to_faculty_blocked_for_plain_staff():
    url = reverse("admin:rsm_thrive_answerreview_changelist")
    fac, _ = _client_for("THRIVE Faculty", "fac-rev")
    assert fac.get(url).status_code == 200
    plain, _ = _client_for(None, "plain-rev")
    assert plain.get(url).status_code == 403


@pytest.mark.django_db
def test_faculty_records_a_correction():
    from rsm_thrive.admin_modules.oversight import AnswerCorrection

    profile = testing.make_student("stud-corr")
    conversation = testing.make_conversation(profile, destination="courses")
    message = testing.make_message(conversation, role="thrive", body="Take MGTA 461.")
    turn = testing.make_turn_log(message, route="factual",
                                 question="Which electives for data science?")

    client, faculty = _client_for("THRIVE Faculty", "fac-corr")
    url = reverse("admin:rsm_thrive_answerreview_change", args=[turn.pk])
    data = {
        "corrections-TOTAL_FORMS": "1",
        "corrections-INITIAL_FORMS": "0",
        "corrections-MIN_NUM_FORMS": "0",
        "corrections-MAX_NUM_FORMS": "1000",
        "corrections-0-id": "",
        "corrections-0-note": "MGTA 461 is spring-only; not an option this quarter.",
        "_save": "Save",
    }
    resp = client.post(url, data)
    assert resp.status_code in (200, 302)
    saved = AnswerCorrection.objects.filter(turn=turn)
    assert saved.count() == 1
    assert saved.first().author_id == faculty.id
