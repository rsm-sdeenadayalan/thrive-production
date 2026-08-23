import pytest

from rsm_thrive.models import JobPosting
from rsm_thrive.services.embeddings import FakeEmbeddings
from rsm_thrive.services.jobs.ingest import ingest_from
from rsm_thrive.services.jobs.sources import FakeJobSource, JobSource

pytestmark = pytest.mark.django_db


def _row(external_id="1", title="Data Analyst", description="SQL and Tableau"):
    return {"external_id": external_id, "title": title, "company": "Acme",
            "location": "SD", "url": "https://e.example/1",
            "description": description, "posted_at": None}


class ExplodingSource(JobSource):
    name = "boom"

    def fetch(self):
        raise RuntimeError("network down")


class TestIngest:
    def test_creates_with_skills_and_embedding(self):
        result = ingest_from([FakeJobSource([_row()])], embeddings=FakeEmbeddings())
        assert result["ingested"] == 1
        posting = JobPosting.objects.get()
        assert posting.source == "fake"
        assert "sql" in posting.skills and "tableau" in posting.skills
        assert len(posting.embedding) > 0 and posting.active

    def test_rerun_updates_not_duplicates(self):
        ingest_from([FakeJobSource([_row()])], embeddings=FakeEmbeddings())
        ingest_from([FakeJobSource([_row(title="Senior Data Analyst")])],
                    embeddings=FakeEmbeddings())
        assert JobPosting.objects.count() == 1
        assert JobPosting.objects.get().title == "Senior Data Analyst"

    def test_stale_postings_deactivate(self):
        ingest_from([FakeJobSource([_row("1"), _row("2")])],
                    embeddings=FakeEmbeddings())
        ingest_from([FakeJobSource([_row("1")])], embeddings=FakeEmbeddings())
        assert JobPosting.objects.get(external_id="1").active
        assert not JobPosting.objects.get(external_id="2").active

    def test_failed_source_skipped_and_its_rows_kept_active(self):
        ingest_from([FakeJobSource([_row()])], embeddings=FakeEmbeddings())
        result = ingest_from([ExplodingSource(), FakeJobSource([_row()])],
                             embeddings=FakeEmbeddings())
        assert result["failed_sources"] == ["boom"]
        assert JobPosting.objects.get().active  # fake source refreshed it
