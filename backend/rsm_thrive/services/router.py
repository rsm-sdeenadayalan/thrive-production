"""One place that decides how a course question gets answered.

Routing used to be scattered: a regex in `grounded_course_advisor`, the
interview's own state machine in `planner.next_intake_step`, a vocabulary check
in `electives.is_course_question`, and a chain of `if` branches in
`bots.answer_electives` that each knew about the next. Nothing named the
decision, so nothing could be tested, logged or corrected as a decision.

This names it. `classify` returns one route and how it was arrived at; the
orchestrator dispatches on that and nothing else.

## Rules first, model second

Most questions do not need a round trip. "Prerequisites for MGTA 452" names a
course and asks a catalog question — that is a rule, it costs nothing, and it
cannot drift. So a small set of confident rules runs first, and the model is
asked only about what is left.

The two are kept distinguishable on purpose. A rule's `confidence` is None, not
1.0: a rule is not a probability, and recording it as one would make the two
indistinguishable in the trace view that exists to tell them apart — and it is
the model-decided routes whose accuracy anyone will ever want to measure.

## Unclear is a route

The one case that earns a follow-up question. Everything else answers; a
question comes back only when proceeding would mean guessing which of two very
different answers the student wanted. That is the whole difference between an
assistant and a form: the form asks first and always, this asks last and rarely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from rsm_thrive.services.electives import (catalog_version, load_careers,
                                            load_catalog)
from rsm_thrive.services.grounded_course_advisor.advisor import (
    _target_field, is_industry_course_question,
)
from rsm_thrive.services.llm import parse_llm_json

ROLE = "role"
INDUSTRY = "industry"
FACTUAL = "factual"
COMBINATION = "combination"
SITUATIONAL = "situational"
QUARTER = "quarter"
CAREERS = "careers"
CATALOG = "catalog"
OUT_OF_SCOPE = "out-of-scope"
UNCLEAR = "unclear"
# Not a kind of question -- a statement that we could not reach the model to
# decide what kind it was. Kept as its own route so an outage is visible in
# the trace view instead of being counted as whatever it fell back to.
DEGRADED = "degraded"

ROUTES = frozenset({ROLE, INDUSTRY, FACTUAL, COMBINATION, SITUATIONAL,
                    QUARTER, OUT_OF_SCOPE, UNCLEAR, DEGRADED})

# Below this, the model is not confident enough to act on. A wrong route is not
# a slightly-worse answer -- it is the industry advisor answering a question
# about a prerequisite, or a refusal to a student who asked something we can
# answer well. Asking once is cheaper than either.
MIN_CONFIDENCE = 0.55


@dataclass
class Route:
    name: str
    #: None when a rule decided. A float only when the model did.
    confidence: float | None = None
    #: The curated `careers.json` id, when the question named a covered role.
    role_id: str = ""
    #: The student's own words for a role we have no bundle for.
    unmatched_role: str = ""
    #: The industry or field named, in the student's own words.
    industry: str = ""
    #: The student's own words for a single quarter they asked about.
    quarter: str = ""
    #: How the decision was reached, for the trace view.
    why: str = ""


# A department prefix from the catalog itself, not any two-to-four letters.
# The loose form matched "does 464" -- "does" being a four-letter word next to
# a number -- which routed correctly by accident and would have routed "week
# 101" the same way. A bare number is handled separately and deterministically
# below, because "does 464 have prerequisites" is a real question a student
# asks and 464 IS a course in this catalog.
COURSE_CODE = re.compile(r"\b(MGTA|MGTF|MGT|CSE)\s*(\d{3}[A-Z]?)\b",
                         re.IGNORECASE)
_BARE_NUMBER = re.compile(r"\b(\d{3}[A-Z]?)\b", re.IGNORECASE)


@lru_cache(maxsize=4)
def _course_numbers_for(_version):
    """The numeric half of every catalog code, e.g. {"451", "464", "251A"}."""
    numbers = set()
    for course in load_catalog():
        parts = course["code"].split()
        if len(parts) == 2:
            numbers.add(parts[1].upper())
        for alias in course.get("also_known_as") or []:
            alias_parts = str(alias).split()
            if len(alias_parts) == 2:
                numbers.add(alias_parts[1].upper())
    return frozenset(numbers)


def _course_numbers():
    return _course_numbers_for(catalog_version())


def names_a_course(question):
    """Does this name a course, by code or by bare number?

    The bare-number half is checked against the CATALOG rather than against a
    pattern, so "464" resolves and "101" does not. That is the difference
    between reading a student's shorthand and pattern-matching any three
    digits in a sentence.
    """
    text = question or ""
    if COURSE_CODE.search(text):
        return True
    numbers = _course_numbers()
    return any(match.group(1).upper() in numbers
               for match in _BARE_NUMBER.finditer(text))

# Words that make a question about a course a FACTUAL one: it asks what the
# catalog or the syllabus says, not what to take.
_FACTUAL_WORDS = frozenset("""
prerequisite prerequisites prereq prereqs corequisite units unit credits
credit offered offering offer run runs quarter quarters term terms season
syllabus grading graded assessment assessed workload textbook instructor
professor taught teaches meets schedule when what who how many
""".split())

# A student describing WHERE THEY ARE. Both halves are required: "I switched"
# on its own could be about a laptop, and "winter" on its own is a season.
_POSITION_WORDS = re.compile(
    r"\b(switch(?:ed|ing)?|transferr?(?:ed|ing)?|moved|already in|currently in|"
    r"i'?m in|im in|behind|catch up|caught up|left|remaining|remain|finish|"
    r"finishing|graduat\w*|on time|drop(?:ped)?|withdrew|retake|retaking|"
    r"deferred|leave of absence|part[- ]time)\b", re.IGNORECASE)
_PROGRAMME_WORDS = re.compile(
    r"\b(11[- ]month|17[- ]month|track|quarter|quarters|winter|spring|fall|"
    r"summer|units|unit|degree|programme|program|plan of study)\b",
    re.IGNORECASE)


@lru_cache(maxsize=4)
def _role_titles_for(_version):
    """Every job title the catalog curates, longest first.

    Longest first because "product data scientist" and "data scientist" are
    both titles and both present in the same sentence; matching the short one
    first would file a Product Analyst question under Data Scientist.
    """
    titles = []
    for role_id, role in load_careers().items():
        for title in (role.get("titles") or []):
            titles.append((str(title).lower(), role_id))
        label = str(role.get("short_label") or "").lower()
        if label:
            titles.append((label, role_id))
    return sorted(titles, key=lambda row: -len(row[0]))


def _role_titles():
    return _role_titles_for(catalog_version())


# A word this long may be off by one character and still be the same word.
# Below it, one edit is too much of the word to guess at: "sql" and "sal" are
# not the same thing, and neither are "ml" and "al".
_FUZZY_FLOOR = 4


def _within_one_edit(said, wanted):
    """Is `said` `wanted` with one character added, dropped, changed or swapped?

    A bounded check rather than a full edit-distance table: the answer is only
    ever needed for "is this the same word", the bound is 1, and the whole
    thing is a walk down two strings.

    Adjacent SWAPS count, which a plain edit distance would score as two
    changes. They are the commonest typo there is -- "anlayst" for "analyst",
    "sceintist" for "scientist" -- and excluding them left the most likely
    mistake as the one thing this could not read.
    """
    if said == wanted:
        return True
    if len(wanted) < _FUZZY_FLOOR or abs(len(said) - len(wanted)) > 1:
        return False
    if len(said) == len(wanted):
        differing = [i for i, (a, b) in enumerate(zip(said, wanted)) if a != b]
        if len(differing) == 1:
            return True
        return (len(differing) == 2 and differing[1] == differing[0] + 1
                and said[differing[0]] == wanted[differing[1]]
                and said[differing[1]] == wanted[differing[0]])
    shorter, longer = sorted((said, wanted), key=len)
    return any(longer[:i] + longer[i + 1:] == shorter for i in range(len(longer)))


def role_match(question):
    """(role id, was it exact?) for the curated role this question names.

    ("", False) when it names none.

    THE quality floor. "I want to be a data scientist" resolves here, off
    `careers.json`, and never reaches a model — the curated mapping is
    authoritative and must not become probabilistic.

    Exact matching runs first and alone decides whenever it can. A student who
    MISTYPES a title is still naming it, though: measured live, "17 month data
    nalyst" was read as a track and no goal at all, so the student was asked
    for the career they had just given. So a second pass allows one character
    of slop per word, and REPORTS that it did — the caller confirms a fuzzy
    match back rather than acting on it silently, because guessing which of
    fourteen careers someone meant is exactly the guess this module refuses to
    make quietly.

    One-word titles are exempt from the slop. "consultant" is too easy to hit
    by accident once a character is free, and it is short enough to type right.
    """
    text = " ".join((question or "").lower().split())
    if not text:
        return "", False
    titles = _role_titles()
    for title, role_id in titles:
        if re.search(rf"\b{re.escape(title)}\b", text):
            return role_id, True
    said = re.findall(r"[a-z]+", text)
    for title, role_id in titles:
        wanted = title.split()
        if len(wanted) < 2:
            continue
        if all(any(_within_one_edit(word, target) for word in said)
               for target in wanted):
            return role_id, False
    return "", False


def matched_role(question):
    """The curated role id this question names, or ""."""
    return role_match(question)[0]


# Words that name a JOB rather than a domain. Used only to decide whether to
# CONFIRM a reading back, never to decide what a career is -- a miss here costs
# one extra line of confirmation, where a miss in `role_match` would cost a
# student the wrong career. That asymmetry is what makes a closed list the
# right tool here and the wrong one there.
_JOB_FUNCTIONS = frozenset("""
analyst analysts analytics scientist scientists engineer engineers manager
managers consultant consultants developer developers specialist specialists
coordinator coordinators associate associates lead leads director directors
officer officers strategist strategists modeller modeler statistician actuary
researcher researchers architect architects administrator advisor planner
planners intern trainee auditor accountant economist technologist
""".split())


# The shapes English gives a job: -ist, -eer, -ian, -ant, -or, -er. Enough on
# their own for the words no list will ever contain -- biologist, sommelier,
# archivist, statistician -- which is what stops this becoming the enumeration
# problem the list above nearly is. Five characters minimum, so "other" and
# "over" do not qualify as careers.
_JOB_SUFFIX = re.compile(r"(ist|eer|ian|ant|or|er)$")


def names_a_job_function(question):
    """Did the student name a job, or only an area?

    "supply chain analyst" names one; "something in supply chain" does not,
    and the second matched a curated career off its short label alone --
    handing back a full recommendation for a career the student had gestured
    at rather than chosen.

    Used only to decide whether to ASK or confirm, never to decide what a
    career is. A miss costs one extra turn; a miss in `role_match` would cost
    a student the wrong career, which is why a word list is the right tool
    here and the wrong one there.
    """
    words = {word for word in re.findall(r"[a-z]+", (question or "").lower())}
    if words & _JOB_FUNCTIONS:
        return True
    if any(len(word) >= 5 and _JOB_SUFFIX.search(word) for word in words):
        return True
    # And a misspelling of one. "esports analsyt" names a job as clearly as
    # "esports analyst" does, and neither the list nor the suffix sees it --
    # "analsyt" ends in "yt". Being asked to clarify a job you named and
    # merely mistyped is the interrogation this whole check exists to avoid.
    return any(_within_one_edit(word, function)
               for word in words if len(word) >= _FUZZY_FLOOR
               for function in _JOB_FUNCTIONS)


# One quarter, planned on its own. "What should I take in Winter?" is a
# planning request scoped to a term -- not a catalog question about which
# electives happen to run then, which is why a first-person planning phrase is
# required and not just the season's name.
_PLAN_ONE_QUARTER = re.compile(
    r"\b(?:"
    r"plan(?:ning)?\s+(?:my|out|just)|just\s+plan|"
    r"(?:what|which)\s+(?:should|do|am|would)\s+i\s+(?:be\s+)?tak\w+|"
    r"should\s+i\s+take|what\s+do\s+i\s+take|what\s+am\s+i\s+taking|"
    r"my\s+(?:summer|fall|winter|spring)|"
    r"(?:just|only)\s+(?:the\s+)?(?:summer|fall|winter|spring)|"
    r"(?:tak\w+|schedul\w+|fill)\s+(?:in|for)\s+(?:the\s+)?"
    r"(?:summer|fall|winter|spring)"
    r")\b", re.IGNORECASE)


# A greeting, and nothing else. Deterministic because it has to be: a model
# call to classify "hi" costs a round trip (measured at 1.8s on this backend)
# to learn something a set membership test knows, and it is the very first
# thing a lot of students type.
_GREETINGS = frozenset("""
hi hii hiya hey heya hello helo yo sup morning afternoon evening
thanks ta cheers ok okay k sure right cool nice
""".split()) | {
    "good morning", "good afternoon", "good evening", "how are you",
    "how's it going", "hows it going", "what's up", "whats up",
    "hi there", "hey there", "hello there", "thank you", "thanks a lot",
}


def is_greeting(question):
    """A whole message that is only a greeting or an acknowledgement."""
    lowered = re.sub(r"[^a-z' ]+", " ", (question or "").lower())
    lowered = " ".join(lowered.split())
    return bool(lowered) and lowered in _GREETINGS


def named_quarter(question):
    """The quarter this question is about, in the student's words, or "".

    Deliberately loose about the TRACK. Which quarter keys exist depends on it
    ("fall-two" only on the 17-month track) and the router does not know the
    student, so the words are captured here and resolved against the real
    track by `planner.resolve_quarter` in the handler -- which returns None
    rather than guessing when they do not fit.
    """
    match = re.search(
        r"\b(summer(?:\s+iii)?|fall(?:\s*\(?\s*second\s+year\s*\)?)?|"
        r"second\s+fall|fall\s+two|winter|spring)\b",
        question or "", re.IGNORECASE)
    return " ".join(match.group(1).split()).lower() if match else ""


def _words(question):
    return {word.strip(".,/-?!'\"") for word in (question or "").lower().split()}


def _is_situational(question):
    text = question or ""
    return bool(_POSITION_WORDS.search(text) and _PROGRAMME_WORDS.search(text))


# "what jobs do you have", "which careers do you cover", "list the roles".
#
# A closed question with a closed answer -- fourteen rows in `careers.json` --
# so it never needs a model, and asking one to place it produced a clarifying
# question instead of the list. The catch is that the words overlap almost
# entirely with a REQUEST ("what courses do you have for a data scientist"), so
# both halves have to match and nothing may name a role, a course or a field.
_CAREER_NOUNS = re.compile(
    r"\b(careers?|jobs?|roles?|professions?|job titles?|career paths?)\b",
    re.IGNORECASE)
_INVENTORY_VERBS = re.compile(
    r"\b(have|offer|support|cover|know|list|available|there|options?|"
    r"suggest|recommend|help with|do you do)\b", re.IGNORECASE)
# Words that turn "what jobs..." into a question about a PARTICULAR job, which
# is the role route's, not this one's.
_NOT_INVENTORY = re.compile(
    r"\b(for|in|as|about|towards?|into|require|need|pay|salary|skills?)\b",
    re.IGNORECASE)


def asks_which_careers(question):
    """True for "which careers do you know", false for "what does X need"."""
    text = question or ""
    if not (_CAREER_NOUNS.search(text) and _INVENTORY_VERBS.search(text)):
        return False
    if _NOT_INVENTORY.search(text) or names_a_course(text):
        return False
    return not matched_role(text)


# "what courses do you have", "what classes can I take", "what's in the
# catalog". Like `asks_which_careers`, a closed question with a closed answer,
# and one a model reliably UNDER-answers: handed 86 rows it replies "86 courses,
# 6 core and 80 electives, all others are electives", which is arithmetic the
# student can already see and none of the context they asked for.
_COURSE_NOUNS = re.compile(
    r"\b(courses?|classes|electives?|catalog|curriculum|offerings?)\b", re.IGNORECASE)
# Wider than the careers rule's, because a catalog gets asked about in more
# ways than a career list does -- "show me", "what can I take", "what have you
# got". "in" stays OUT of the exclusions' reach only here; "courses IN finance"
# is still excluded below, because it names a field.
_CATALOG_VERBS = re.compile(
    r"\b(have|has|is|are|offer|offers|support|cover|covers|know|list|available|there|"
    r"options?|show|see|browse|take|get|access|hold|holds|include|includes|"
    r"all|everything|full|entire|whole)\b", re.IGNORECASE)


# "in the catalog", "in the programme" -- a container, not a subject area.
_OUR_CONTAINER = re.compile(
    r"\bin\s+(?:the\s+)?(?:catalog|curriculum|programme|program|msba|"
    r"course\s+list)\b", re.IGNORECASE)


def asks_which_courses(question):
    """True for "what courses do you have", false for "what should I take"."""
    text = question or ""
    if not (_COURSE_NOUNS.search(text) and _CATALOG_VERBS.search(text)):
        return False
    # A course, a role or a field named makes this a question about THAT, which
    # the factual, role and industry routes answer better than a list does.
    if names_a_course(text) or matched_role(text):
        return False
    # `_NOT_INVENTORY` blocks "in", which is right for "courses IN finance" and
    # wrong for "what is IN the catalog" -- the second one names our own
    # container, not a field. Strip that reading before testing.
    without_container = _OUR_CONTAINER.sub(" ", text)
    if _NOT_INVENTORY.search(without_container):
        return False
    return True


def rule_route(question):
    """A confident route, decided here, or None to ask the model.

    Order matters and is argued, not arbitrary:

    1. **Situational first.** "I switched to the 11-month track, what do I take
       to finish?" names no course and no role, but a later rule would happily
       read "take" as a catalog question. Where a student is standing changes
       what every other route would answer.
    2. **A named course with a catalog word** is factual. Nothing about "does
       MGTA 464 have prerequisites" is a recommendation request, and paying for
       a model call to learn that is the round trip this whole layer exists to
       avoid.
    3. **A curated role** is the deterministic path — with an industry named
       alongside it, the combination.

    Anything else goes to the model. In particular a bare industry is NOT ruled
    here even though `is_industry_course_question` would fire: that regex is
    loose enough to claim "what courses do you have", which is not an industry
    question at all, and letting it rule would reinstate the scattered routing
    this module replaces.
    """
    text = question or ""
    if is_greeting(text):
        return Route(UNCLEAR, why="a greeting; nothing to route yet")
    if asks_which_careers(text):
        return Route(CAREERS, why="asked which careers this planner knows")
    if asks_which_courses(text):
        return Route(CATALOG, why="asked what the catalog holds, overall")
    if _is_situational(text):
        return Route(SITUATIONAL, why="named a position in the programme")
    if names_a_course(text) and (_words(text) & _FACTUAL_WORDS):
        return Route(FACTUAL, why="named a course and asked a catalog question")
    # A single quarter, asked about in the first person. After the factual rule
    # on purpose: "does MGTA 464 run in winter" names a course and asks what
    # the catalog says, which is a different question from "what should I take
    # in winter".
    quarter = named_quarter(text)
    if quarter and _PLAN_ONE_QUARTER.search(text):
        return Route(QUARTER, quarter=quarter,
                     why="asked what to take in one named quarter")
    role_id = matched_role(text)
    if role_id:
        # `_target_field`, not `is_industry_course_question`: the latter needs a
        # catalog word ("courses", "electives") before it will look at a field
        # at all, and "data scientist in the food industry" has none -- it was
        # being filed as a plain role question, which is the exact case the
        # combination route exists for.
        field = _target_field(text)
        if field or is_industry_course_question(text):
            return Route(COMBINATION, role_id=role_id, industry=field or "",
                         why="named a curated role and a field")
        return Route(ROLE, role_id=role_id, why="named a curated role")
    return None


CLASSIFY_SYSTEM = (
    "You route one question from a Rady MSBA student to the part of the "
    "advising tool that can answer it. Reply with JSON only: "
    "{\"route\": \"...\", \"confidence\": 0.0-1.0, \"role\": \"...\", "
    "\"industry\": \"...\"}.\n\n"
    "The routes:\n"
    "- \"role\": they named a target job and want courses for it.\n"
    "- \"industry\": they named an industry, sector or field (aerospace, food, "
    "healthcare, sport) and want courses for it. Use this when they named a "
    "FIELD rather than a JOB.\n"
    "- \"combination\": they named BOTH a job and an industry (\"data "
    "scientist in the food industry\").\n"
    "- \"factual\": a question about what a course IS — its prerequisites, "
    "units, term, workload, content, or what the programme requires. Also use "
    "this for questions about the catalog as a whole (\"what electives do you "
    "have\").\n"
    "- \"quarter\": what to take in ONE named quarter (\"what should I take "
    "in Winter?\", \"just plan my spring\"). Put the quarter's name in "
    "\"quarter\".\n"
    "- \"situational\": their own position in the programme — a track switch, "
    "the quarter they are in, falling behind, finishing on time, what is left "
    "to take. Anything that depends on where THEY are.\n"
    "- \"out-of-scope\": not about MSBA courses, this programme, or their "
    "studies at all. Trivia, weather, sport, personal advice, asking you to do "
    "their coursework. Say so plainly rather than answering.\n"
    "- \"unclear\": you genuinely cannot tell, and the answers the routes would "
    "give are very different. Use this sparingly — prefer a route.\n\n"
    "\"role\" is the job in the student's own words, or empty. \"industry\" is "
    "the field in their own words, or empty. \"quarter\" is the term they "
    "named, or empty. \"confidence\" is how sure you are about the route, "
    "honestly.")


def _model_route(llm, question):
    try:
        raw = llm.chat(CLASSIFY_SYSTEM,
                       [{"role": "user", "content": str(question)}],
                       json_mode=True)
    except Exception:
        # SAY the model is unreachable rather than picking a route without it.
        #
        # This used to default to FACTUAL, on the reasoning that a catalog
        # answer is the safest thing to do knowing nothing. What that produced
        # during a real outage was "I don't have catalog or syllabus material
        # that answers that" to every single turn -- a content refusal blaming
        # the corpus for a billing problem. Measured live: both backends went
        # down (a lapsed Codex entitlement and an exhausted TritonAI budget)
        # and the app spent ten turns insisting it had no material.
        return Route(DEGRADED, why="the language model could not be reached")
    parsed = parse_llm_json(raw or "")
    if not isinstance(parsed, dict):
        return Route(UNCLEAR, why="classifier returned nothing usable")
    name = str(parsed.get("route") or "").strip().lower()
    if name not in ROUTES:
        return Route(UNCLEAR, why=f"classifier returned unknown route {name!r}")
    try:
        confidence = float(parsed.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    role_said = str(parsed.get("role") or "").strip()[:60]
    industry = str(parsed.get("industry") or "").strip()[:60]
    quarter = str(parsed.get("quarter") or "").strip()[:40]
    if confidence < MIN_CONFIDENCE and name != OUT_OF_SCOPE:
        # Out of scope is exempt: a low-confidence "this isn't about the
        # programme" still means the model saw nothing it recognised, and
        # asking a clarifying question about the weather is worse than saying
        # plainly that it is not something this tool does.
        return Route(UNCLEAR, confidence, why=f"low confidence on {name!r}")
    route = Route(name, confidence, industry=industry,
                  quarter=quarter or named_quarter(question), why="classified")
    if name in (ROLE, COMBINATION):
        # The model may name a role; only `careers.json` may resolve one. It
        # is asked what the STUDENT said, and the curated table decides whether
        # that is a role we serve -- which is what keeps the deterministic path
        # deterministic even when a model chose the route into it.
        route.role_id = matched_role(role_said) or matched_role(question)
        if not route.role_id:
            route.unmatched_role = role_said
    return route


def classify(llm, question):
    """The route for this question. Rules first, then one model call."""
    ruled = rule_route(question)
    if ruled is not None:
        return ruled
    return _model_route(llm, question)
