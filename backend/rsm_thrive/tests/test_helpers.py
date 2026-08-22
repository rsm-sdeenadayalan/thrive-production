import datetime as dt

import pytest
from django.utils import timezone

from rsm_thrive.serialize import iso_date, iso_instant


def test_iso_instant_localizes_with_offset():
    aware = dt.datetime(2026, 8, 11, 16, 0, tzinfo=dt.timezone.utc)
    out = iso_instant(aware)
    assert out == "2026-08-11T09:00:00-07:00"  # PDT


def test_iso_instant_rejects_naive():
    with pytest.raises(ValueError):
        iso_instant(dt.datetime(2026, 8, 11, 9, 0))


def test_iso_date():
    assert iso_date(dt.date(2026, 8, 11)) == "2026-08-11"


def test_api_login_required_returns_401_json(client):
    # /api/thrive/me does not exist yet; use a tiny throwaway view via RequestFactory.
    from django.test import RequestFactory
    from django.contrib.auth.models import AnonymousUser
    from rsm_thrive.http import api_login_required, json_ok

    @api_login_required
    def view(request):
        return json_ok({"fine": True})

    req = RequestFactory().get("/x")
    req.user = AnonymousUser()
    resp = view(req)
    assert resp.status_code == 401
    import json
    assert json.loads(resp.content)["error"]["code"] == "unauthenticated"
