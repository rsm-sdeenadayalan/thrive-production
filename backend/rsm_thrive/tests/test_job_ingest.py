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


class CountingEmbeddings(FakeEmbeddings):
    """Wraps FakeEmbeddings so tests can assert how many texts were embedded."""

    def __init__(self):
        self.calls = 0

    def embed(self, texts: list) -> list:
        self.calls += len(texts)
        return super().embed(texts)


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

    def test_null_title_ingests_with_empty_title(self):
        row = _row()
        row["title"] = None
        result = ingest_from([FakeJobSource([row])], embeddings=FakeEmbeddings())
        assert result["ingested"] == 1
        assert JobPosting.objects.get().title == ""

    def test_bad_url_row_skipped_sibling_ingests(self):
        bad = _row(external_id="1")
        bad["url"] = "javascript:alert(1)"
        good = _row(external_id="2")
        result = ingest_from([FakeJobSource([bad, good])], embeddings=FakeEmbeddings())
        assert result["ingested"] == 1
        assert JobPosting.objects.count() == 1
        assert JobPosting.objects.get().external_id == "2"

    def test_unchanged_content_skips_reembedding(self):
        embeddings = CountingEmbeddings()
        ingest_from([FakeJobSource([_row()])], embeddings=embeddings)
        first_calls = embeddings.calls
        first_hash = JobPosting.objects.get().content_hash
        assert first_calls == 1
        assert first_hash != ""

        ingest_from([FakeJobSource([_row()])], embeddings=embeddings)
        posting = JobPosting.objects.get()
        assert embeddings.calls == first_calls  # no new embed calls
        assert posting.content_hash == first_hash
        assert posting.active

    def test_changed_description_reembeds_and_updates_hash(self):
        embeddings = CountingEmbeddings()
        ingest_from([FakeJobSource([_row()])], embeddings=embeddings)
        first_hash = JobPosting.objects.get().content_hash

        ingest_from([FakeJobSource([_row(description="SQL, Tableau, and Python")])],
                    embeddings=embeddings)
        posting = JobPosting.objects.get()
        assert embeddings.calls == 2
        assert posting.content_hash != first_hash
        assert posting.description == "SQL, Tableau, and Python"


class TestEmbeddingBackendSwitch:
    """A backend switch must re-embed even when the postings' text is identical.

    The hash-skip optimisation compared content only, so switching
    THRIVE_LLM (or correcting TRITONAI_EMBED_MODEL) left every posting on its
    old, wrong-width vector: `search_postings` logged a dimension mismatch and
    quietly ranked on keyword overlap alone. Re-running ingest -- the remedy the
    README prescribes -- did nothing, because nothing had changed textually.
    """

    def test_stored_vectors_of_another_width_are_reembedded(self):
        class WideEmbeddings(FakeEmbeddings):
            dimension = 64

            def embed(self, texts: list) -> list:
                return [[0.1] * 64 for _ in texts]

        ingest_from([FakeJobSource([_row()])], embeddings=FakeEmbeddings())
        assert len(JobPosting.objects.get().embedding) == FakeEmbeddings.dimension

        # Same rows, same text, different backend: the vector must be replaced.
        ingest_from([FakeJobSource([_row()])], embeddings=WideEmbeddings())
        assert len(JobPosting.objects.get().embedding) == 64

    def test_same_backend_still_skips_reembedding(self):
        embeddings = CountingEmbeddings()
        ingest_from([FakeJobSource([_row()])], embeddings=embeddings)
        after_first = embeddings.calls

        ingest_from([FakeJobSource([_row()])], embeddings=embeddings)
        assert embeddings.calls == after_first
