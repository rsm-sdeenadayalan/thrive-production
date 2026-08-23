import datetime as dt

from rsm_thrive.services.jobs.sources import (
    FakeJobSource, GreenhouseSource, LeverSource, configured_sources, strip_html)


class StubSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        payload = self.payload

        class R:
            def json(self):
                return payload
            def raise_for_status(self):
                pass
        return R()


class TestStripHtml:
    def test_tags_entities_whitespace(self):
        html = "<div><p>SQL &amp; Python</p>\n\n<li>ML</li></div>"
        assert strip_html(html) == "SQL & Python ML"


class TestGreenhouse:
    def test_normalizes(self):
        session = StubSession({"jobs": [{
            "id": 4001, "title": "Data Analyst",
            "location": {"name": "San Diego, CA"},
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/4001",
            "content": "&lt;p&gt;Needs SQL&lt;/p&gt;",
            "updated_at": "2026-08-01T12:00:00-04:00",
        }]})
        [row] = GreenhouseSource("acme", "Acme", session=session).fetch()
        assert row["external_id"] == "4001"
        assert row["company"] == "Acme"
        assert "SQL" in row["description"] and "<p>" not in row["description"]
        assert isinstance(row["posted_at"], dt.datetime)
        assert "boards-api.greenhouse.io/v1/boards/acme/jobs" in session.calls[0][0]


class TestLever:
    def test_normalizes(self):
        session = StubSession([{
            "id": "ab-12", "text": "BI Engineer",
            "categories": {"location": "Remote"},
            "hostedUrl": "https://jobs.lever.co/acme/ab-12",
            "descriptionPlain": "dbt and Snowflake",
            "createdAt": 1754000000000,
        }])
        [row] = LeverSource("acme", "Acme", session=session).fetch()
        assert row["external_id"] == "ab-12"
        assert row["title"] == "BI Engineer"
        assert row["description"] == "dbt and Snowflake"
        assert row["posted_at"].year >= 2025


class TestConfigured:
    def test_builds_from_companies_json(self):
        sources = configured_sources(session=StubSession({"jobs": []}))
        names = {s.name for s in sources}
        assert names == {"greenhouse", "lever"}
        assert len(sources) >= 4

    def test_fake_source_passthrough(self):
        rows = [{"external_id": "x", "title": "t", "company": "c",
                 "location": "", "url": "https://e.example", "description": "d",
                 "posted_at": None}]
        assert FakeJobSource(rows).fetch() == rows
