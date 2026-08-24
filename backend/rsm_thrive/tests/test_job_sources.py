import datetime as dt

from rsm_thrive.services.jobs.sources import (
    AshbySource, FakeJobSource, GreenhouseSource, LeverSource, WorkableSource,
    configured_sources, strip_html)


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


class TestAshby:
    def test_normalizes(self):
        session = StubSession({"jobs": [{
            "id": "op-1", "title": "Data Scientist",
            "location": "Remote",
            "jobUrl": "https://jobs.ashbyhq.com/acme/op-1",
            "descriptionHtml": "<p>Needs Python</p>",
            "publishedAt": "2026-08-01T12:00:00.000Z",
            "isListed": True,
        }]})
        [row] = AshbySource("acme", "Acme", session=session).fetch()
        assert row["external_id"] == "op-1"
        assert row["company"] == "Acme"
        assert row["title"] == "Data Scientist"
        assert row["location"] == "Remote"
        assert row["url"] == "https://jobs.ashbyhq.com/acme/op-1"
        assert "Python" in row["description"] and "<p>" not in row["description"]
        assert isinstance(row["posted_at"], dt.datetime)
        assert "api.ashbyhq.com/posting-api/job-board/acme" in session.calls[0][0]

    def test_skips_unlisted(self):
        session = StubSession({"jobs": [{
            "id": "op-2", "title": "Hidden Role", "location": "Remote",
            "jobUrl": "https://jobs.ashbyhq.com/acme/op-2",
            "descriptionHtml": "<p>Hidden</p>", "publishedAt": None,
            "isListed": False,
        }]})
        rows = AshbySource("acme", "Acme", session=session).fetch()
        assert rows == []


class TestWorkable:
    def test_normalizes(self):
        session = StubSession({"jobs": [{
            "shortcode": "AB123", "title": "BI Analyst",
            "city": "San Diego", "country": "USA",
            "url": "https://apply.workable.com/acme/j/AB123",
            "description": "<p>Needs SQL</p>",
            "published_on": "2026-08-01",
        }]})
        [row] = WorkableSource("acme", "Acme", session=session).fetch()
        assert row["external_id"] == "AB123"
        assert row["company"] == "Acme"
        assert row["title"] == "BI Analyst"
        assert row["location"] == "San Diego, USA"
        assert row["url"] == "https://apply.workable.com/acme/j/AB123"
        assert "SQL" in row["description"] and "<p>" not in row["description"]
        assert isinstance(row["posted_at"], dt.datetime)
        assert "apply.workable.com/api/v1/widget/accounts/acme" in session.calls[0][0]

    def test_falls_back_to_location_field(self):
        session = StubSession({"jobs": [{
            "shortcode": "AB124", "title": "Remote Role",
            "city": None, "country": None, "location": "Remote",
            "url": "https://apply.workable.com/acme/j/AB124",
            "description": "text", "published_on": None,
        }]})
        [row] = WorkableSource("acme", "Acme", session=session).fetch()
        assert row["location"] == "Remote"
        assert row["posted_at"] is None


class TestConfigured:
    def test_builds_from_companies_json(self):
        sources = configured_sources(session=StubSession({"jobs": []}))
        names = {s.name for s in sources}
        assert names == {"greenhouse", "lever", "ashby"}
        assert len(sources) >= 4

    def test_fake_source_passthrough(self):
        rows = [{"external_id": "x", "title": "t", "company": "c",
                 "location": "", "url": "https://e.example", "description": "d",
                 "posted_at": None}]
        assert FakeJobSource(rows).fetch() == rows
