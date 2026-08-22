import datetime as dt

from rsm_thrive.services.zoom import (
    FakeZoomClient, ServerToServerZoomClient, get_zoom_client,
)


def test_fake_client_is_deterministic_and_records():
    fake = FakeZoomClient()
    url1 = fake.create_meeting("Advising", dt.datetime(2026, 9, 1, 16,
                                                       tzinfo=dt.timezone.utc), 30)
    url2 = fake.create_meeting("Advising", dt.datetime(2026, 9, 2, 16,
                                                       tzinfo=dt.timezone.utc), 30)
    assert url1 == url2 and url1.startswith("https://ucsd.zoom.us/j/fake-")
    assert len(fake.calls) == 2


def test_get_zoom_client_env_selection(monkeypatch):
    for var in ("THRIVE_ZOOM_ACCOUNT_ID", "THRIVE_ZOOM_CLIENT_ID",
                "THRIVE_ZOOM_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    assert get_zoom_client() is None
    monkeypatch.setenv("THRIVE_ZOOM_ACCOUNT_ID", "acc")
    monkeypatch.setenv("THRIVE_ZOOM_CLIENT_ID", "cid")
    monkeypatch.setenv("THRIVE_ZOOM_CLIENT_SECRET", "sec")
    client = get_zoom_client()
    assert isinstance(client, ServerToServerZoomClient)


def test_real_client_wraps_failures(monkeypatch):
    import requests
    def boom(*a, **kw):
        raise requests.ConnectionError("no network")
    monkeypatch.setattr("requests.post", boom)
    client = ServerToServerZoomClient("acc", "cid", "sec")
    import pytest
    from rsm_thrive.services.zoom import ZoomError
    with pytest.raises(ZoomError):
        client.create_meeting("t", __import__("datetime").datetime(
            2026, 9, 1, tzinfo=__import__("datetime").timezone.utc), 30)
