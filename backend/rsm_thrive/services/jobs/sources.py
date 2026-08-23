"""Posting sources behind one interface.

Greenhouse and Lever expose public JSON boards — no key, no scraping, and
explicitly served for this purpose. An aggregator source (Adzuna/JSearch)
slots in later behind the same ABC once a key exists (backlog).
"""

import datetime as dt
import html
import json
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from django.utils.dateparse import parse_datetime

_COMPANIES_PATH = Path(__file__).resolve().parents[2] / "data" / "jobs" / "companies.json"
_TAG = re.compile(r"<[^>]+>")


def strip_html(raw):
    text = html.unescape(raw or "")
    text = _TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


class JobSource(ABC):
    name = "abstract"

    @abstractmethod
    def fetch(self):
        """-> list of normalized posting dicts (see module tests)."""


class FakeJobSource(JobSource):
    name = "fake"

    def __init__(self, postings):
        self._postings = postings

    def fetch(self):
        return list(self._postings)


def _session_or_requests(session):
    if session is not None:
        return session
    import requests
    return requests.Session()


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def __init__(self, board, company, session=None):
        self.board = board
        self.company = company
        self._session = session

    def fetch(self):
        session = _session_or_requests(self._session)
        url = (f"https://boards-api.greenhouse.io/v1/boards/"
               f"{self.board}/jobs?content=true")
        response = session.get(url, timeout=20)
        response.raise_for_status()
        rows = []
        for job in response.json().get("jobs", []):
            rows.append({
                "external_id": str(job["id"]),
                "title": job.get("title", ""),
                "company": self.company,
                "location": (job.get("location") or {}).get("name", ""),
                "url": job.get("absolute_url", ""),
                "description": strip_html(job.get("content", "")),
                "posted_at": parse_datetime(job.get("updated_at") or "") or None,
            })
        return rows


class LeverSource(JobSource):
    name = "lever"

    def __init__(self, company_slug, company, session=None):
        self.slug = company_slug
        self.company = company
        self._session = session

    def fetch(self):
        session = _session_or_requests(self._session)
        url = f"https://api.lever.co/v0/postings/{self.slug}?mode=json"
        response = session.get(url, timeout=20)
        response.raise_for_status()
        rows = []
        for job in response.json():
            created = job.get("createdAt")
            posted = (dt.datetime.fromtimestamp(created / 1000, tz=dt.timezone.utc)
                      if created else None)
            rows.append({
                "external_id": str(job["id"]),
                "title": job.get("text", ""),
                "company": self.company,
                "location": (job.get("categories") or {}).get("location", "") or "",
                "url": job.get("hostedUrl", ""),
                "description": job.get("descriptionPlain")
                               or strip_html(job.get("description", "")),
                "posted_at": posted,
            })
        return rows


@lru_cache(maxsize=1)
def _companies():
    return json.loads(_COMPANIES_PATH.read_text())


def configured_sources(session=None):
    config = _companies()
    sources = [GreenhouseSource(e["board"], e["company"], session=session)
               for e in config.get("greenhouse", [])]
    sources += [LeverSource(e["slug"], e["company"], session=session)
                for e in config.get("lever", [])]
    return sources
