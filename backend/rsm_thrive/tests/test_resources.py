import pytest

from rsm_thrive.testing import make_resource, make_student

pytestmark = pytest.mark.django_db


def test_resources_shape_and_order(client):
    profile = make_student()
    make_resource(id="r2", title="Zoom help", category="technical")
    make_resource(id="r1", title="CMC coaching", category="career",
                  owner="Rady Career Management")

    client.force_login(profile.user)
    body = client.get("/api/thrive/resources").json()
    assert [r["id"] for r in body] == ["r1", "r2"]  # career < technical
    assert body[0] == {
        "id": "r1", "title": "CMC coaching", "description": "What this is for.",
        "url": "https://rady.ucsd.edu/", "category": "career",
        "owner": "Rady Career Management",
    }
    assert "owner" not in body[1]
