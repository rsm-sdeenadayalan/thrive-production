import pytest

from rsm_thrive.testing import enroll, make_course, make_skill, make_student

pytestmark = pytest.mark.django_db


def test_skills_shape_and_order(client):
    profile = make_student()
    course = make_course(id="c1")
    enroll(profile, course)
    sql = make_skill(profile, name="SQL", source="course", course=course)
    ab = make_skill(profile, name="A/B Testing")
    other = make_student(username="other")
    make_skill(other, name="Theirs")

    client.force_login(profile.user)
    body = client.get("/api/thrive/resume/skills").json()
    assert [s["name"] for s in body] == ["A/B Testing", "SQL"]
    assert body[1] == {"id": f"skill-{sql.pk}", "name": "SQL",
                       "source": "course", "courseId": "c1"}
    assert "courseId" not in body[0]
