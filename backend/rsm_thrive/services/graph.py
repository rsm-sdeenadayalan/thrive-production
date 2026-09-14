"""Microsoft Graph (Outlook) calendar integration. Optional: only active once
an advisor has connected an account, on top of `MS_GRAPH_*` env config.

Never log access_token/refresh_token values, in requests, responses, or
GraphError details.
"""
import datetime as dt
import os

import msal
import requests
from django.core import signing

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
STATE_SALT = "rsm_thrive.services.graph.state"
STATE_MAX_AGE_SECONDS = 600
DEFAULT_SCOPES = "Calendars.ReadWrite offline_access User.Read"
TOKEN_REFRESH_SKEW_SECONDS = 60


class GraphError(Exception):
    pass


def graph_enabled() -> bool:
    return bool(
        os.environ.get("MS_GRAPH_CLIENT_ID")
        and os.environ.get("MS_GRAPH_TENANT_ID")
        and os.environ.get("MS_GRAPH_CLIENT_SECRET")
    )


def _scopes() -> list:
    return os.environ.get("MS_GRAPH_SCOPES", DEFAULT_SCOPES).split()


def _redirect_uri() -> str:
    return os.environ.get("MS_GRAPH_REDIRECT_URI", "")


def _msal_app() -> msal.ConfidentialClientApplication:
    tenant_id = os.environ["MS_GRAPH_TENANT_ID"]
    return msal.ConfidentialClientApplication(
        os.environ["MS_GRAPH_CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=os.environ["MS_GRAPH_CLIENT_SECRET"],
    )


def sign_state(advisor_id: str) -> str:
    return signing.dumps(advisor_id, salt=STATE_SALT)


def verify_state(state: str):
    try:
        return signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None


def build_auth_url(advisor_id: str, state: str) -> str:
    return _msal_app().get_authorization_request_url(
        _scopes(), state=state, redirect_uri=_redirect_uri(),
    )


def _account_email(access_token: str) -> str:
    try:
        resp = requests.get(
            f"{GRAPH_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"$select": "mail,userPrincipalName"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise GraphError(str(exc)) from exc
    body = resp.json()
    return body.get("mail") or body.get("userPrincipalName") or ""


def exchange_code(code: str) -> dict:
    result = _msal_app().acquire_token_by_authorization_code(
        code, scopes=_scopes(), redirect_uri=_redirect_uri(),
    )
    if "access_token" not in result:
        raise GraphError(result.get("error_description", "token exchange failed"))
    access_token = result["access_token"]
    expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(
        seconds=result.get("expires_in", 0))
    return {
        "access_token": access_token,
        "refresh_token": result.get("refresh_token", ""),
        "expires_at": expires_at,
        "account_email": _account_email(access_token),
    }


def refresh(conn) -> str:
    result = _msal_app().acquire_token_by_refresh_token(
        conn.refresh_token, scopes=_scopes(),
    )
    if "access_token" not in result:
        raise GraphError(result.get("error_description", "token refresh failed"))
    conn.access_token = result["access_token"]
    if result.get("refresh_token"):
        conn.refresh_token = result["refresh_token"]
    conn.expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(
        seconds=result.get("expires_in", 0))
    conn.save(update_fields=["access_token", "refresh_token", "expires_at", "updated_at"])
    return conn.access_token


def _valid_access_token(conn) -> str:
    skew = dt.timedelta(seconds=TOKEN_REFRESH_SKEW_SECONDS)
    if conn.expires_at <= dt.datetime.now(dt.UTC) + skew:
        return refresh(conn)
    return conn.access_token


def _connection_or_none(advisor):
    return getattr(advisor, "calendar_connection", None)


def get_busy_periods(advisor, start, end) -> list:
    conn = _connection_or_none(advisor)
    if conn is None or not graph_enabled():
        return []
    token = _valid_access_token(conn)
    try:
        resp = requests.get(
            f"{GRAPH_BASE}/me/calendarView",
            headers={"Authorization": f"Bearer {token}",
                     "Prefer": 'outlook.timezone="UTC"'},
            params={
                "startDateTime": start.astimezone(dt.UTC).isoformat(),
                "endDateTime": end.astimezone(dt.UTC).isoformat(),
                "$select": "start,end,showAs",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise GraphError(str(exc)) from exc
    periods = []
    for event in resp.json().get("value", []):
        if event.get("showAs") == "free":
            continue
        periods.append((_parse_graph_datetime(event["start"]),
                        _parse_graph_datetime(event["end"])))
    return periods


def _parse_graph_datetime(field: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(field["dateTime"]).replace(tzinfo=dt.UTC)


def create_event(advisor, appointment):
    conn = _connection_or_none(advisor)
    if conn is None or not graph_enabled():
        return None
    token = _valid_access_token(conn)
    slot = appointment.slot
    location = (appointment.zoom_join_url
                if slot.mode == "zoom" and appointment.zoom_join_url
                else advisor.location)
    content = (f"THRIVE {advisor.service} appointment with {appointment.student.username}.\n"
              f"Mode: {slot.mode}\n"
              f"Reason: {appointment.reason}\n")
    if slot.mode == "zoom" and appointment.zoom_join_url:
        content += f"Join: {appointment.zoom_join_url}\n"
    body = {
        "subject": f"THRIVE: {advisor.name} & {appointment.student.username}",
        "body": {"contentType": "Text", "content": content},
        "start": {"dateTime": slot.start.astimezone(dt.UTC).isoformat(),
                  "timeZone": "UTC"},
        "end": {"dateTime": slot.end.astimezone(dt.UTC).isoformat(),
                "timeZone": "UTC"},
        "location": {"displayName": location},
    }
    try:
        resp = requests.post(
            f"{GRAPH_BASE}/me/events",
            headers={"Authorization": f"Bearer {token}"},
            json=body, timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise GraphError(str(exc)) from exc
    return resp.json().get("id", "")
