import pytest

from rsm_thrive.testing import enroll, make_course, make_requirement, make_student

pytestmark = pytest.mark.django_db


def test_prefill_shape_and_course_format(client):
    profile = make_student(display_name="Ada Lovelace", goal="Data Scientist")
    make_requirement("11 month", units_required=50)
    c1 = make_course(id="c1", code="MGTA 453", title="Business Analytics", units=4)
    c2 = make_course(id="c2", code="MGTA 495", title="Special Topics", units=2)
    done = make_course(id="c3", code="MGTA 400", title="Done Course", units=4)
    enroll(profile, c1)
    enroll(profile, c2)
    enroll(profile, done, completed=True)

    client.force_login(profile.user)
    body = client.get("/api/thrive/requests/prefill").json()
    assert body == {
        "studentName": "Ada Lovelace",
        "program": "MSBA",
        "track": "11 month",
        "term": "Fall 2026",
        "currentCourses": ["MGTA 400 · Done Course", "MGTA 453 · Business Analytics",
                           "MGTA 495 · Special Topics"],
        "currentUnits": 10,
        "unitsCompleted": 4,
        "unitsRequired": 50,
    }


def test_prefill_unseeded_degree_503(client):
    profile = make_student()
    client.force_login(profile.user)
    resp = client.get("/api/thrive/requests/prefill")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "not_configured"
