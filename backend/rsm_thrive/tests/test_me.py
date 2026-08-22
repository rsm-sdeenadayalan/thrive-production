import pytest

from rsm_thrive.testing import make_student

pytestmark = pytest.mark.django_db


def test_me_requires_login(client):
    assert client.get("/api/thrive/me").status_code == 401


def test_me_returns_student_shape(client):
    profile = make_student(
        username="ada",
        display_name="Ada Lovelace",
        goal="Data Scientist",
        track="11 month",
        consent_lms_read=True,
    )
    client.force_login(profile.user)
    body = client.get("/api/thrive/me").json()
    assert body == {
        "id": "ada",
        "name": "Ada Lovelace",
        "goal": "Data Scientist",
        "track": "11 month",
        "program": "MSBA",
        "standingSummary": "You're on track.",
        "standing": "onTrack",
        "consent": {
            "calendarRead": False,
            "lmsRead": True,
            "careerRecommendations": False,
            "advisorSharing": False,
        },
        "currentTerm": "Fall 2026",
        "programStart": "2026-08-01",
    }
    # avatarUrl is optional in the contract: omitted when blank.
    assert "avatarUrl" not in body
