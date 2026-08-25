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

    def test_lexical_tier_admits_a_chunk_the_cosine_gate_would_refuse(self):
        """The screenshot bug: "How do i get zoom?" refused a page about Zoom.

        `min_similarity=0.99` stands in for "cosine says no" without depending
        on what FakeEmbeddings happens to score, so this asserts the TIER, not
        a similarity number that a model swap would move.
        """
        _doc("canvas#zoom", "Zoom- Set Up Your UCSD Pro Account", "policy",
             ["resources"], [
                 ("Zoom", "Activate your UCSD Zoom Pro account before class."),
             ])

        assert retrieve("zoom", "resources", top_k=5, min_similarity=0.99) == []

        hits = retrieve("zoom", "resources", top_k=5, min_similarity=0.99,
                        lexical_min=1.0)
        assert [c.document.title for c, _ in hits] == [
            "Zoom- Set Up Your UCSD Pro Account"]

    def test_lexical_tier_requires_every_distinctive_term(self):
        """A PARTIAL word match must not open the gate.

        This is the property that keeps the refusal rule intact: "recipe for
        lasagna" shares `recipe` with a food page and still gets nothing,
        because `lasagna` is not there too.
        """
        _doc("crawled#food", "FOOD & HOUSING", "scraped", ["resources"], [
            ("Pantry", "The Hub pantry shares a recipe box with students."),
        ])

        assert retrieve("recipe for lasagna", "resources", top_k=5,
                        min_similarity=0.99, lexical_min=1.0) == []
        assert retrieve("recipe box", "resources", top_k=5,
                        min_similarity=0.99, lexical_min=1.0) != []

    def test_lexical_tier_off_by_default_leaves_behaviour_unchanged(self):
        _doc("canvas#zoom", "Zoom Setup", "policy", ["resources"], [
            ("Zoom", "Activate your UCSD Zoom Pro account before class."),
        ])
        assert retrieve("zoom", "resources", top_k=5, min_similarity=0.99) == []

    def test_lexical_tier_reports_the_real_cosine_not_a_blend(self):
        """A rescued chunk reports its actual cosine, below min_similarity.

        Everything downstream -- prompts, ChatTurnLog, eval output -- reads
        this number as a cosine. Reporting the blended rank instead would
        quietly redefine what every logged score means.
        """
        _doc("canvas#zoom", "Zoom Setup", "policy", ["resources"], [
            ("Zoom", "Activate your UCSD Zoom Pro account before class."),
        ])
        [(chunk, score)] = retrieve("zoom", "resources", top_k=5,
                                    min_similarity=0.99, lexical_min=1.0)
        assert score < 0.99

    def test_a_question_with_no_distinctive_terms_cannot_use_the_lexical_tier(self):
        """All-stopword questions score 0.0, so the tier cannot fire at all."""
        _doc("crawled#any", "Anything", "scraped", ["resources"], [
            ("Any", "Some text about fees and deadlines."),
        ])
        assert retrieve("what is it", "resources", top_k=5,
                        min_similarity=0.99, lexical_min=1.0) == []

    def test_typo_in_the_question_still_finds_the_page(self):
        """"zooom" retrieved nothing about Zoom before typo tolerance.

        The lexical tier needs EVERY query term present in one chunk, so one
        misspelling closed it entirely — not for want of the page, but because
        the corpus spells the product correctly.
        """
        _doc("canvas#zoom", "Zoom Setup", "policy", ["resources"], [
            ("Zoom", "Activate your UCSD zoom pro account before class."),
        ])
        hits = retrieve("zooom", "resources", top_k=5, min_similarity=0.99,
                        lexical_min=1.0)
        assert [c.document.title for c, _ in hits] == ["Zoom Setup"]

    def test_a_correctly_spelled_word_is_never_rewritten(self):
        """A word that IS in the corpus stays itself, even if another corpus
        word is one edit away — otherwise a real term gets "corrected" into a
        different real term and the answer silently changes topic."""
        from rsm_thrive.services.retrieval import expand_terms

        vocabulary = frozenset({"calender", "calendar"})
        [group] = expand_terms(["calender"], vocabulary)
        assert group == frozenset({"calender"})

    def test_short_words_are_matched_exactly(self):
        """Under 5 characters an edit turns one real word into another — "fees"
        is one edit from "feed" — so the rule would do more harm than good."""
        from rsm_thrive.services.retrieval import expand_terms

        [group] = expand_terms(["fees"], frozenset({"feed", "fees"}))
        assert group == frozenset({"fees"})

    def test_typo_expansion_only_offers_words_the_corpus_actually_has(self):
        from rsm_thrive.services.retrieval import expand_terms

        [group] = expand_terms(["zooom"], frozenset({"zoom", "unrelated"}))
        assert group == frozenset({"zooom", "zoom"})

    def test_lexical_floor_refuses_a_single_word_match_at_absurd_similarity(self):
        """The "who is the president" leak: one common word present in a chunk
        is not evidence the chunk answers the question."""
        _doc("crawled#fellow", "Fellowships", "scraped", ["resources"], [
            ("Awards", "Nominations are endorsed by the university president."),
        ])
        # No floor: the word alone opens the gate however unrelated the chunk.
        assert retrieve("president", "resources", top_k=5, min_similarity=0.99,
                        lexical_min=1.0) != []
        # With a floor, the same match is refused.
        assert retrieve("president", "resources", top_k=5, min_similarity=0.99,
                        lexical_min=1.0, lexical_floor=0.99) == []

    def test_lexical_floor_defaults_to_letting_the_tier_through(self):
        _doc("canvas#zoom", "Zoom Setup", "policy", ["resources"], [
            ("Zoom", "Activate your UCSD zoom pro account before class."),
        ])
        assert retrieve("zoom", "resources", top_k=5, min_similarity=0.99,
                        lexical_min=1.0) != []

    def test_keyword_score_accepts_grouped_spellings(self):
        from rsm_thrive.services.retrieval import keyword_score

        chunk = _doc("t#kw", "T", "policy", ["resources"], [
            ("H", "activate your zoom account"),
        ]).chunks.first()
        assert keyword_score(["zoom"], chunk) == pytest.approx(1.0)
        assert keyword_score([frozenset({"zooom", "zoom"})], chunk) == pytest.approx(1.0)
        assert keyword_score(["zooom"], chunk) == 0.0

    def test_top_k_caps(self):
        chunks = [(f"h{i}", f"course drop deadline detail number {i}") for i in range(4)]
        _doc("handbook#many", "MSBA Handbook", "policy", ["resources"], chunks)
        hits = retrieve("course drop deadline", "resources",
                        top_k=2, min_similarity=0.0)
        assert len(hits) == 2
        assert hits[0][1] >= hits[1][1]
