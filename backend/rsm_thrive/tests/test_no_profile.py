import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

PROFILE_ENDPOINTS = [
    ("get", "/api/thrive/me"),
    ("get", "/api/thrive/events"),
    ("get", "/api/thrive/degree/timeline"),
    ("get", "/api/thrive/degree/progress"),
    ("get", "/api/thrive/requests/prefill"),
    ("get", "/api/thrive/tss"),
    ("post", "/api/thrive/tss/connect"),
    ("post", "/api/thrive/resume/versions"),
]


@pytest.mark.parametrize("method,path", PROFILE_ENDPOINTS)
def test_profileless_user_gets_403_not_500(client, method, path):
    bare = get_user_model().objects.create_user(username="staffonly")
    client.force_login(bare)
    resp = getattr(client, method)(path)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "no_profile"
