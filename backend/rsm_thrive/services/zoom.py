"""Zoom meeting creation. Real client uses Server-to-Server OAuth; the fake
is for tests and for environments without credentials (VINCENT-ASKS #8)."""
import datetime as dt
import os

import requests


class ZoomError(Exception):
    pass


class FakeZoomClient:
    def __init__(self):
        self.calls = []

    def create_meeting(self, topic: str, start: dt.datetime,
                       duration_minutes: int) -> str:
        self.calls.append((topic, start, duration_minutes))
        return f"https://ucsd.zoom.us/j/fake-{abs(hash(topic)) % 10**9}"


class ServerToServerZoomClient:
    def __init__(self, account_id: str, client_id: str, client_secret: str):
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret

    def _token(self) -> str:
        resp = requests.post(
            "https://zoom.us/oauth/token",
            params={"grant_type": "account_credentials",
                    "account_id": self.account_id},
            auth=(self.client_id, self.client_secret),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def create_meeting(self, topic: str, start: dt.datetime,
                       duration_minutes: int) -> str:
        try:
            token = self._token()
            resp = requests.post(
                "https://api.zoom.us/v2/users/me/meetings",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "topic": topic,
                    "type": 2,
                    "start_time": start.astimezone(dt.timezone.utc)
                                       .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "duration": duration_minutes,
                    "timezone": "UTC",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["join_url"]
        except requests.RequestException as exc:
            raise ZoomError(str(exc)) from exc


def get_zoom_client():
    account_id = os.environ.get("THRIVE_ZOOM_ACCOUNT_ID")
    client_id = os.environ.get("THRIVE_ZOOM_CLIENT_ID")
    client_secret = os.environ.get("THRIVE_ZOOM_CLIENT_SECRET")
    if account_id and client_id and client_secret:
        return ServerToServerZoomClient(account_id, client_id, client_secret)
    return None
