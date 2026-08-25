"""Top-k chunk retrieval scoped to a destination.

Hybrid, not purely vector. The vector half finds paraphrases; the keyword half
finds the chunk that literally contains "parking permit" or "$21,279.39".

Why both, measured 2026-08-24 on the real corpus with TritonAI
`api-tgpt-embeddings`: cosine alone put the chunks holding the Rady fee amounts
outside the top FOURTEEN for "what does the MSBA cost per quarter and when is
payment due?", because a chunk of pipe-table rows has almost no lexical overlap
with a natural-language question, while prose chunks that merely mention fees
scored 0.68. The embedding model itself is fine (identical text 0.9999,
unrelated 0.11-0.32); the failure is specific to dense, number-heavy chunks —
exactly the ones carrying deadlines and dollar figures, i.e. the facts a
student acts on.

The blend is deliberately conservative: cosine still dominates ranking, and the
keyword term can only lift a chunk that shares distinctive words with the
question.

Admission is two-tier, and the second tier exists because cosine alone is not
measurable on SHORT questions. Measured 2026-08-24 on the shipped corpus, the
same document scores 0.840 for "How do I set up my UCSD Zoom Pro account?" and
0.531 for "How do i get zoom?" — below the 0.55 gate, so the bot refused a
question its own corpus answers on page one. That 0.55 was calibrated against
the persona probe sets, whose questions are full prose; a student types three
words. Worse, at that length the ordering inverts: for "library hours" the
right page (UC San Diego Library Tours, which contains both words) sits at
0.350 while "About Student Financial Solutions" sits at 0.447. Absolute cosine
is tracking how well-formed the QUESTION is, not whether the chunk answers it.

So a chunk is also admitted when it contains EVERY distinctive term of the
question (`keyword_score >= lexical_min`, i.e. 1.0), whatever its cosine. That
is a much stronger claim than the ranking blend makes: not "shares some words"
but "the question's whole vocabulary is in this passage". It is what rescues
"how do i get zoom", "library hours", "transcript request" and "counseling
services", and it is why the refusal rule survives — "what is the recipe for
lasagna" needs one chunk holding both `recipe` AND `lasagna`, and there is
none. Swept against 13 must-refuse controls (the 3 in faq_golden.json plus 10
off-corpus questions), this tier leaked zero. Replacing it with a cosine floor
plus a PARTIAL keyword match was tried and rejected: it bought no additional
coverage and at 0.40 it leaked 3 of the 13. (That is a different knob from
`lexical_floor`, which does not relax the "every term present" rule — it only
declines to apply it at absurdly low similarity.)

The lexical tier then needed two guards of its own, both added after measuring
100 deliberately unclear questions:

* `lexical_floor`, because "every term present" means little when there is only
  ONE term. "who is the president" was admitted at cosine 0.222 off the word
  "president" appearing in a Fellowships page, and the bot answered from that
  chunk rather than refusing.
* typo tolerance, because the tier demands EXACT term presence, so one
  misspelling closed it completely — "zooom" retrieved nothing about Zoom, not
  for want of the page but because the corpus spells the product correctly.
  Coverage on those 100 questions went from 46/70 to 52/70 with no loss on
  well-formed phrasing.

`min_similarity` still gates the cosine tier exactly as it did, and
KEYWORD_WEIGHT still only affects ranking — sweeping it above 0.25 made
coverage worse, not better.
"""

import math
import re


from rsm_thrive.models import DocumentChunk
from rsm_thrive.services.embeddings import cosine, get_embeddings

# Question-shaped words carry no signal about which chunk answers them.
STOPWORDS = frozenset("""
a an the and or but if then than of to in on at by for with from as is are was
were be been being it its this that these those i me my we our you your they
them their he she his her do does did done have has had having can could should
would will shall may might must not no nor so about into over under out up down
off across per via more most other some such only own same too very just also
all any each few both what which who whom when where how why get got need want
""".split())

WORD_RE = re.compile(r"[a-z0-9][a-z0-9$.,/-]*")

# Weight on the keyword half. 0.25 was chosen so a perfect keyword match can
# outrank a cosine gap of ~0.25 (wide enough to rescue the fee tables, narrow
# enough that ranking stays embedding-led).
KEYWORD_WEIGHT = 0.25


def _terms(text):
    """Distinctive lowercase terms in a string, stopwords removed."""
    return {
        word.strip(".,/-")
        for word in WORD_RE.findall((text or "").lower())
        if len(word) > 2 and word not in STOPWORDS
    }


# Only words this long are typo-corrected. Measured on the misspellings students
# actually type: every one of "zooom", "trascript", "electves", "laptp",
# "orentation", "counsling", "internshp", "imunizations", "finacial", "sylabus"
# is edit-distance 1 from the right corpus term. Below 5 characters the rule
# stops being safe rather than stops being useful -- "fees" is one edit from
# "feed", "drop" from "drip" -- so short words are matched exactly.
MIN_FUZZY_LENGTH = 5

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"

# Rebuilding the corpus vocabulary on every question would mean a second full
# scan per query, so it is cached against (chunk count, highest pk): both move
# when anything is ingested, and ingestion is the only thing that changes it.
def vocabulary_of(haystacks):
    """Every distinctive term in the chunks under consideration.

    Deliberately NOT cached. The first version keyed a module-level cache on
    (chunk count, highest pk); both of those can repeat — pytest rolls each
    test's transaction back and SQLite reuses pks — so one test was scored
    against the vocabulary of the previous one. A cache whose key can collide
    silently serves the wrong answer, and retrieval already tokenises every
    chunk in order to score it, so the vocabulary costs nothing extra if it
    reuses that work rather than repeating it.

    Scoped to the destination being searched, so a question asked of the FAQ
    bot is never "corrected" into a word that exists only in the career corpus.
    """
    terms = set()
    for haystack in haystacks:
        terms |= haystack
    return frozenset(terms)


def _edits1(word):
    """Every string one edit (delete/transpose/replace/insert) from `word`."""
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    return set(
        [a + b[1:] for a, b in splits if b]
        + [a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1]
        + [a + c + b[1:] for a, b in splits if b for c in _ALPHABET]
        + [a + c + b for a, b in splits for c in _ALPHABET]
    )


def expand_terms(query_terms, vocabulary):
    """Group each query term with the corpus spellings it might be a typo of.

    Returns one frozenset per term: the term itself, plus any corpus word one
    edit away IF the term does not appear in the corpus at all. A word that is
    already in the corpus is never "corrected" -- "calender" really does occur
    in a UCSD page, so it stays itself rather than being rewritten to
    "calendar".

    Generating the ~1,500 strings one edit from a word and intersecting them
    with the vocabulary is far cheaper than comparing the word against 11,774
    vocabulary entries, and it is exact rather than a similarity heuristic.

    Why this matters: the lexical admission tier requires every query term to
    appear in one chunk, so a single misspelled word closed the gate entirely.
    "zooom" retrieved nothing about Zoom -- not because the corpus lacks the
    page, but because it spells the product correctly.
    """
    groups = []
    for term in query_terms:
        candidates = {term}
        if term not in vocabulary and len(term) >= MIN_FUZZY_LENGTH:
            candidates |= _edits1(term) & vocabulary
        groups.append(frozenset(candidates))
    return groups


def _as_groups(query_terms):
    """Accept either bare terms or already-grouped spellings."""
    return [frozenset([t]) if isinstance(t, str) else frozenset(t) for t in query_terms]


def _score(groups, haystack):
    """Fraction of the question's distinctive terms present in one haystack."""
    if not groups or not haystack:
        return 0.0
    hits = sum(1 for group in groups if group & haystack)
    # sqrt keeps a couple of shared words from scoring as high as a full match
    # while still rewarding the first hits generously.
    return math.sqrt(hits / len(groups))


def keyword_score(query_terms, chunk):
    """Fraction of the question's distinctive terms present in this chunk.

    Scored against heading + text, because the heading is often where the
    describing words live ("Registration fees by quarter for ...").
    """
    return _score(_as_groups(query_terms),
                  _terms(f"{chunk.heading or ''} {chunk.text or ''}"))


def retrieve(query, destination, top_k, min_similarity, lexical_min=None,
             lexical_floor=0.0, embeddings=None):
    """Top-k (chunk, cosine) pairs for `query`, scoped to one bot's corpus.

    A chunk is admitted if EITHER its cosine clears `min_similarity` (the
    embedding-led tier, unchanged) OR its keyword score clears `lexical_min`
    — every distinctive term of the question present in that one chunk. See
    the module docstring for the measurement behind the second tier.

    `lexical_floor` is the minimum cosine the lexical tier will accept. It
    gates only that tier; the cosine tier still uses `min_similarity` alone.
    Measured 2026-08-24, 0.40 removes the "who is the president" class of leak
    at no cost to coverage, while 0.45 and 0.50 start dropping real answers
    (terse coverage 98 -> 96 -> 93), so the floor is deliberately low: it is a
    sanity floor, not a relevance gate.

    `lexical_min=None` disables the lexical tier and restores the pure-cosine
    behaviour exactly, which is what the tests that predate it assert.

    The returned score is the COSINE similarity, not the blended rank score:
    callers (bot prompts, eval output, ChatTurnLog) already interpret it that
    way, and reporting a blended number would silently change what
    `min_similarity` means to everyone reading the logs. A chunk admitted by
    the lexical tier therefore reports a cosine BELOW `min_similarity`, which
    is honest: that is the number, and the reason it was kept is not that
    number.
    """
    embeddings = embeddings or get_embeddings()
    [query_vector] = embeddings.embed([query])
    # Tokenise each in-scope chunk ONCE and keep it: the vocabulary and the
    # keyword score both need it, and scoring used to redo this work per chunk.
    scoped, haystacks = [], []
    for chunk in DocumentChunk.objects.select_related("document"):
        if destination not in (chunk.document.destinations or []):
            continue
        scoped.append(chunk)
        haystacks.append(_terms(f"{chunk.heading or ''} {chunk.text or ''}"))

    # Group each term with the corpus spellings it may be a misspelling of, so
    # one typo cannot close the lexical tier on an answerable question.
    query_terms = expand_terms(_terms(query), vocabulary_of(haystacks))

    scored = []
    for chunk, haystack in zip(scoped, haystacks):
        similarity = cosine(query_vector, chunk.embedding)
        keyword = _score(query_terms, haystack)
        # Two tiers, either of which admits. A question with no distinctive
        # terms at all scores 0.0 here, so it can only ever enter on cosine.
        lexical_hit = (lexical_min is not None and keyword >= lexical_min
                       and similarity >= lexical_floor)
        if similarity < min_similarity and not lexical_hit:
            continue
        rank = similarity + KEYWORD_WEIGHT * keyword
        scored.append((chunk, similarity, rank))

    scored.sort(key=lambda triple: -triple[2])
    return [(chunk, similarity) for chunk, similarity, _ in scored[:top_k]]
