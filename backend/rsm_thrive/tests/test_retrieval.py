import pytest

from rsm_thrive.models import Document, DocumentChunk
from rsm_thrive.services.embeddings import FakeEmbeddings, cosine, get_embeddings
from rsm_thrive.services.retrieval import retrieve

pytestmark = pytest.mark.django_db


def _doc(source, title, kind, destinations, chunks):
    emb = FakeEmbeddings()
    doc = Document.objects.create(source=source, title=title, kind=kind,
                                  destinations=destinations)
    vectors = emb.embed([text for _, text in chunks])
    for seq, ((heading, text), vector) in enumerate(zip(chunks, vectors)):
        DocumentChunk.objects.create(document=doc, seq=seq, heading=heading,
                                     text=text, embedding=vector)
    return doc


class TestFakeEmbeddings:
    def test_deterministic_and_normalized(self):
        emb = FakeEmbeddings()
        [a1] = emb.embed(["drop a course after week two"])
        [a2] = emb.embed(["drop a course after week two"])
        assert a1 == a2
        assert abs(sum(x * x for x in a1) - 1.0) < 1e-9

    def test_overlap_scores_higher_than_disjoint(self):
        emb = FakeEmbeddings()
        query, near, far = emb.embed([
            "dropping a course deadline",
            "the deadline for dropping a course is week two",
            "zoom meeting links for appointments",
        ])
        assert cosine(query, near) > cosine(query, far)

    def test_get_embeddings_is_fake_under_tests(self):
        assert isinstance(get_embeddings(), FakeEmbeddings)


class TestRetrieve:
    def test_ranks_filters_and_scopes_by_destination(self):
        _doc("handbook#drop", "MSBA Handbook", "policy", ["resources"], [
            ("Dropping a course", "Students may drop a course before the end of week two without a W."),
        ])
        _doc("syllabus#456", "MGTA 456 Syllabus", "syllabus", ["resources", "courses"], [
            ("Overview", "Supply chain analytics with optimization models."),
        ])
        _doc("career#resume", "Resume Guide", "scraped", ["career"], [
            ("Length", "Keep the resume to one page for analytics roles."),
        ])

        hits = retrieve("when can I drop a course", "resources",
                        top_k=5, min_similarity=0.0)
        assert hits and hits[0][0].document.title == "MSBA Handbook"
        titles = [chunk.document.title for chunk, _ in hits]
        assert "Resume Guide" not in titles  # career-only doc never leaks

    def test_min_similarity_filters_everything_thin(self):
        _doc("handbook#x", "MSBA Handbook", "policy", ["resources"], [
            ("Laptops", "Laptop loans are handled by the tech desk."),
        ])
        assert retrieve("quantum entanglement", "resources",
                        top_k=5, min_similarity=0.99) == []

    def test_top_k_caps(self):
        chunks = [(f"h{i}", f"course drop deadline detail number {i}") for i in range(4)]
        _doc("handbook#many", "MSBA Handbook", "policy", ["resources"], chunks)
        hits = retrieve("course drop deadline", "resources",
                        top_k=2, min_similarity=0.0)
        assert len(hits) == 2
        assert hits[0][1] >= hits[1][1]
