"""The FAQ and career bots, and the pieces a plan of study is maintained with.

The courses surface no longer has a bot function here. It is dispatched by
`services/orchestrator.py`, which routes a question and then calls the
helpers below for the operations a student performs on a plan they already
have -- swapping a course, walking it a quarter at a time, finalising it.

What went with the interview: `_extract_intake`, `_aside` and
`_retitle_if_button_pressed` existed only because the courses bot opened
with four scripted questions and had to cope with a student asking something
else during them. There is no script to interrupt now, so the aside is just
the factual route and the retitle is unnecessary -- a conversation opened by
typing a real sentence already has a better title than any of them composed.
"""

from dataclasses import dataclass, field

from rsm_thrive.services import planner
from rsm_thrive.services.bot_config import bot_config
from rsm_thrive.services.electives import load_catalog
from rsm_thrive.services.llm import parse_llm_json
from rsm_thrive.services.retrieval import retrieve


@dataclass
class BotReply:
    body: str
    chunk_ids: list = field(default_factory=list)
    model_note: str = "llm"
    # Choices to offer as buttons alongside this reply. Empty for a free-text
    # answer; a question with a fixed set of answers should not require typing.
    quick_replies: list = field(default_factory=list)
    # A small form to offer instead, when one control per item beats a row of
    # buttons. None for every other reply. See `planner.rating_form_for`.
    form: dict | None = None
    # Which route the orchestrator took to produce this, and how sure it was.
    # `route_confidence` stays None when a rule decided, because a rule has no
    # confidence to report and recording 1.0 would make the two look alike in
    # the report that exists to tell them apart. See `services/router.py`.
    route: str = ""
    route_confidence: float | None = None
    # This turn declined to answer. Set at every site that declines, rather
    # than inferred downstream from `model_note`, because the refusal report is
    # a content backlog and a backlog assembled by parsing prose loses rows
    # silently the first time the prose changes.
    refused: bool = False
    # The plan this reply renders, for a caller that needs to inspect what was
    # actually scheduled rather than re-derive it. Set only by `_plan_reply`;
    # None everywhere else. See `orchestrator._uncurated_coverage_note`, which
    # measures coverage against the courses that survived the unit limits, and
    # would otherwise have to rebuild the plan to find out what they were.
    plan: dict | None = None


def build_context(hits):
    lines = []
    for n, (chunk, _score) in enumerate(hits, start=1):
        title = chunk.document.title
        head = f"[{n}] {title} — {chunk.heading}" if chunk.heading else f"[{n}] {title}"
        lines.append(f"{head}\n{chunk.text}")
    return "\n\n".join(lines)


def append_sources(body, hits):
    """Append the sources behind an answer, as links where a URL is known.

    A student who is about to act on a deadline should be able to open the page
    that states it — "Sources: Registration Fees" is a claim, a link is
    checkable. Documents ingested without a `source_url` (fixtures, pasted
    material) still list by title alone.

    One source stays inline; several become a bulleted list. A comma-joined run
    was fine at three sources and unreadable at ten — a single line holding
    "Where to Find MSBA Plans of Study, Course Schedules and Syllabi, Analytical
    Writing Program — awp.ucsd.edu, How to Enroll in Individual Classes at
    UCSD (Community College and CSU Students) — students.ucsd.edu, ..." cannot
    be scanned, and worse, the titles themselves contain commas, so the reader
    cannot tell where one source ends and the next begins. `top_k` for the FAQ
    bot is 10, so ten is the normal case, not the pathological one.

    The list is Markdown the frontend already renders: `RichMessage` turns `- `
    lines into a real `<ul>` and parses links inside list items, so this arrives
    as clickable bullets rather than as literal hyphens.
    """
    if not hits:
        return body
    seen, entries = set(), []
    for chunk, _score in hits:
        document = chunk.document
        if document.title in seen:
            continue
        seen.add(document.title)
        url = (document.source_url or "").strip()
        entries.append(f"[{document.title}]({url})" if url else document.title)
    if len(entries) == 1:
        return f"{body}\n\nSource: {entries[0]}"
    listed = "\n".join(f"- {entry}" for entry in entries)
    return f"{body}\n\nSources:\n{listed}"


def _trimmed(history, config):
    return history[-config["max_history_turns"]:]


def answer_faq(llm, question, history):
    config = bot_config("faq")
    hits = retrieve(question, "resources", config["top_k"],
                    config["min_similarity"], config.get("lexical_min"),
                    config.get("lexical_floor", 0.0))
    if not hits:
        return _answer_from_the_web(llm, config, question, history)
    system = f"{config['system_prompt']}\n\nContext passages:\n\n{build_context(hits)}"
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    body = llm.chat(system, messages)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "llm")


WEB_FALLBACK_SYSTEM = (
    "You are THRIVE, the assistant for UC San Diego Rady's MSBA program. Rady's "
    "own material does not cover this question, so you may search the web for "
    "it.\n\n"
    "Return ONLY a JSON object: {\"answerable\": true|false, \"reply\": \"...\"}.\n\n"
    "Set answerable to FALSE, with reply empty, when the question is not "
    "something a student would ask about their studies, this campus, or their "
    "career -- general trivia, sport, weather, entertainment -- or when it asks "
    "you to do their academic work for them.\n\n"
    "Otherwise set answerable to TRUE and put the answer in reply, following "
    "these rules:\n"
    "- NEVER state Rady or MSBA policy as settled fact. Deadlines, fees, unit "
    "counts, prerequisites and approval chains come from advising, not from the "
    "web. Where the question turns on one, say what you found, say it is "
    "unofficial, and send them to MSBA advising to confirm.\n"
    "- Be concise and concrete, and say what kind of source you drew on.\n"
    "- Do not claim to be quoting Rady or UCSD material.")

WEB_DISCLAIMER = (
    "_Rady's own material doesn't cover this, so the above comes from a web "
    "search rather than program documentation. Please verify anything you act "
    "on — and for anything about policy, deadlines, fees or approvals, confirm "
    "with MSBA advising (bookable from the **Appointments** tab)._")


def _answer_from_the_web(llm, config, question, history):
    """No corpus hit: search the web and label the answer as unofficial.

    The spec's rule was a flat refusal here, on the grounds that "a confident
    wrong policy answer is worse than none". That reasoning is about POLICY, and
    it is kept -- the prompt refuses to state a deadline, fee or approval chain
    as settled, and routes those to advising either way. What it was also doing
    was refusing questions the corpus simply has not got to yet: "What is
    VMock?" is a real Rady careers tool whose page is band C in the scorecard
    and therefore not ingested, and a student asking about it got sent to
    advising for something a web search answers in a sentence.

    Two things this must never do. It must not cite: `chunk_ids` stays empty and
    no Source line is appended, because attributing a web answer to Rady
    material is the exact defect that made "2 plus 2 is 4" arrive with a course
    citation attached. And it must not turn the bot into a general chatbot --
    the model classifies the question first, and the golden set's weather, sport
    and write-my-essay cases still refuse.

    Anything unexpected -- a failed call, unparseable output, an empty answer --
    falls back to the refusal. Failing closed keeps the old guarantee intact
    for every case this path cannot confidently improve on.
    """
    if not config.get("web_fallback", True):
        return BotReply(config["refusal_reply"], [], "refusal", refused=True)
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    try:
        raw = llm.search_chat(WEB_FALLBACK_SYSTEM, messages, True)
    except Exception:
        return BotReply(config["refusal_reply"], [], "refusal", refused=True)
    parsed = parse_llm_json(raw or "")
    body = str(parsed.get("reply") or "").strip()
    # `parse_llm_json` degrades unparseable output to {"reply": <raw text>}, so
    # a missing verdict means the classification never happened. Refuse rather
    # than pass prose through as though it had been judged in scope.
    if not parsed.get("answerable") or not body:
        return BotReply(config["refusal_reply"], [], "refusal", refused=True)
    return BotReply(f"{body}\n\n{WEB_DISCLAIMER}", [], "web")


def answer_career(llm, question, history):
    # OURS, deliberately. The bots port took only the FAQ bot and the course
    # recommender; the career bot stays on our own retrieval call, without the
    # lexical tier its config does not configure.
    config = bot_config("career")
    hits = retrieve(question, "career", config["top_k"], config["min_similarity"])
    system = config["system_prompt"]
    if hits:
        system = f"{system}\n\nContext passages:\n\n{build_context(hits)}"
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    body = llm.chat(system, messages)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "llm")


def _catalog_entry(course):
    """One course as the model should see it: the fields, not prose about them."""
    seasons = sorted({o["season"] for o in course.get("offerings") or []})
    lines = [f"{course['code']} — {course['title']} ({course['units']} units, "
             f"{'core' if course['is_core'] else 'elective'})"]
    if seasons:
        lines.append(f"  offered: {', '.join(seasons)}")
    for label, key in (("prerequisites", "prerequisites"), ("workload", "workload"),
                       ("grading", "grading"), ("notes", "notes")):
        value = course.get(key)
        if value:
            lines.append(f"  {label}: {value}")
    for label, key in (("topics", "topics"), ("skills", "skills"), ("tools", "tools")):
        value = course.get(key)
        if value:
            lines.append(f"  {label}: {', '.join(value)}")
    if course.get("description"):
        lines.append(f"  about: {course['description']}")
    return "\n".join(lines)


def _catalog_context(question):
    """The catalog rows this question is about, or None if it is not about any.

    Grounded in `data/catalog/courses.json` rather than the document corpus,
    because that file IS the answer to a course question -- it carries units,
    seasons, prerequisites, tools and workload as fields, where a retrieved
    prose chunk carries whatever a web page happened to say. Retrieval also
    answered questions this bot has no business answering: asked about tuition
    it found a fee page and replied, which is the FAQ bot's job on a different
    tab.
    """
    from rsm_thrive.services import electives

    courses = electives.search_catalog(question)
    if courses:
        return "\n\n".join(_catalog_entry(course) for course in courses)
    if not electives.is_course_question(question):
        return None
    # A course question that names nothing in particular. "What have you got?",
    # "which have no prerequisites" and "which run in winter" are all answered
    # by the WHOLE catalog rather than by six arbitrary rows -- and a code list
    # cannot answer any of them, which is what it used to return. Thirty-one
    # one-line entries is a small context and lets the model actually look.
    overview = electives.catalog_overview()
    # WHICH PROGRAMMES, not just which codes. Asked "what courses do you have
    # access to", a student wants to know they can reach past the MSBA's own
    # courses into CSE, MBA and MFin ones, and on what terms -- a code list
    # answers none of that.
    programmes = "\n".join(
        f"- {p['name']} ({p['prefix']}): {p['total']} courses "
        f"({p['core']} core, {p['electives']} elective) — {p['terms']}"
        for p in overview["programmes"])
    rows = []
    for course in electives.load_catalog():
        seasons = sorted({o["season"] for o in course.get("offerings") or []})
        rows.append(
            f"{course['code']} — {course['title']} | {course['units']}u | "
            f"{'core' if course['is_core'] else 'elective'} | "
            f"offered {', '.join(seasons) or 'unlisted'} | "
            f"prereq {course.get('prerequisites') or 'none'} | "
            f"workload {course.get('workload') or 'unlisted'}")
    return (f"The catalog holds {overview['total']} courses: "
            f"{overview['core']} core and {overview['electives']} electives, "
            f"drawn from these programmes:\n{programmes}\n"
            f"Up to {overview['nonMsbaCap']} of the 28 elective units may come "
            f"from outside the MSBA's own courses.\n\n"
            + "\n".join(rows))


def _divergence_note(answers, plan):
    """What a student on a fixed route has dropped out of their bundle.

    The design document is explicit that a recommendation which does not say
    what it gives up is not a recommendation. On a fixed route the bundle IS
    the recommendation, so swapping an anchor course out is exactly the moment
    to say so -- once, plainly, without refusing the swap.
    """
    from rsm_thrive.services import bundles

    # The plan's OWN account of which fill it got, not the intake's request.
    # A bundle that turned out to be unschedulable falls back to the ranked
    # fill, and reading the request instead gave that plan a "you have moved
    # off the recommended bundle" warning about an edit the student never made.
    if plan.get("route") != "fixed":
        return ""
    goals = answers.get("goals") or []
    missing = bundles.divergence(plan, goals[0]) if goals else []
    if not missing:
        return ""
    names = ", ".join(f"**{code}**" for code in missing)
    return (f"\n\n> You have moved off the recommended bundle: {names} "
            f"{'is' if len(missing) == 1 else 'are'} part of what makes this a "
            f"plan for that path. Still your call — say the word and I'll put "
            f"{'it' if len(missing) == 1 else 'them'} back.")


def _plan_reply(user, answers, selections=None):
    """`selections` pins courses chosen outside the scorer -- the web-matched
    set for a career the catalog curates no bundle for."""
    record = planner.save_intake(user, answers)
    if selections:
        record.selections = selections
        record.save(update_fields=["selections", "updated_at"])
    plan = planner.build_for(answers, planner.taken_course_ids(user), selections)
    body = planner.render_plan_markdown(plan) + _divergence_note(answers, plan)
    body += ("\n\nWant to go through it a quarter at a time? I'll show what "
             "else fits each elective slot and what each one teaches, so you "
             "can swap before you finalise.")
    return BotReply(body, [], "plan", planner.review_intro_replies(answers),
                    plan=plan)


def _review_reply(conversation, user, answers, index):
    """Show one quarter of the review and remember where we are.

    The index is CLAMPED before it is stored. `review_quarter` clamps its own
    copy, so the right quarter was always rendered -- but the raw index went
    into the session, so a student pressing "next quarter" past the end walked
    the counter up for ever. Nothing visible broke; the state simply stopped
    describing anything, and every later read of it had to re-clamp to be safe.
    """
    taken = planner.taken_course_ids(user)
    record = planner.save_intake(user, answers)
    plan = planner.build_for(answers, taken, record.selections)
    index = max(0, min(index, len(plan["quarters"]) - 1))
    body, replies, _last = planner.review_quarter(plan, answers, index, taken)
    session = planner.save_session_intake(conversation, answers)
    session.review = {"index": index}
    session.save(update_fields=["review", "updated_at"])
    return BotReply(body, [], "review", replies)


def _finalise_reply(conversation, user, answers):
    taken = planner.taken_course_ids(user)
    record = planner.save_intake(user, answers)
    plan = planner.build_for(answers, taken, record.selections)
    session = planner.save_session_intake(conversation, answers)
    session.review = None
    session.save(update_fields=["review", "updated_at"])
    return BotReply(planner.finalised_markdown(plan), [], "plan")


def _handle_change_request(user, answers, question):
    """A message naming courses, once a plan already exists.

    Two shapes are useful and both are common: naming ONE course in the plan
    means "show me alternatives to this", and naming a second course as well
    means "make the swap". Anything else falls through to rebuilding the plan.
    """
    codes = planner.mentioned_codes(question)
    if not codes:
        return None

    record = planner.save_intake(user, answers)
    plan = planner.build_for(answers, planner.taken_course_ids(user),
                              record.selections)
    quarter_key, slot, row = None, None, None
    for code in codes:
        quarter_key, slot, row = planner.locate_code(plan, code)
        if row is not None:
            break
    if row is None:
        return None

    replacement = next((c for c in codes if c.upper() != (row["code"] or "").upper()),
                       None)
    if replacement:
        target = next((course["id"] for course in load_catalog()
                       if course["code"].upper() == replacement.upper()), None)
        try:
            record.selections = planner.apply_swap(
                answers, record.selections, quarter_key, slot, target,
                planner.taken_course_ids(user))
        except ValueError as exc:
            return BotReply(
                f"I can't put **{replacement}** in that slot: {exc}.", [], "plan")
        record.save(update_fields=["selections", "updated_at"])
        updated = planner.build_for(answers, planner.taken_course_ids(user),
                                     record.selections)
        return BotReply(
            f"Swapped **{row['code']}** for **{replacement}**.\n\n"
            + planner.render_plan_markdown(updated), [], "plan")

    return BotReply(planner.render_alternatives_markdown(
        planner.alternatives_for(plan, answers, quarter_key, slot,
                                 planner.taken_course_ids(user))), [], "plan")



# Deterministic, like `review_intent`: a short closed list beats a model call.
_PLAN_REQUESTS = ("show me the plan", "show the plan", "show my plan", "print it",
                  "print the plan", "the plan again", "see it again", "again",
                  "full plan", "whole plan", "rebuild", "redo it", "start over",
                  "my plan")


def _wants_the_plan(question):
    """Did the student ask to SEE the plan of study?"""
    lowered = (question or "").strip().lower()
    return any(phrase in lowered for phrase in _PLAN_REQUESTS)


def _explain_course(user, answers, question):
    """Why a named course is in this plan, using the reasons already recorded.

    The engine writes a `reasons` list onto every elective row as it picks it,
    so the explanation is the scorer's own account rather than a second story
    told about it afterwards. Returns None when the question names no course in
    the plan, so the caller can fall through.
    """
    codes = planner.mentioned_codes(question)
    if not codes:
        return None
    record = planner.save_intake(user, answers)
    plan = planner.build_for(answers, planner.taken_course_ids(user),
                              record.selections)
    for code in codes:
        quarter_key, _slot, row = planner.locate_code(plan, code)
        if row is None:
            continue
        quarter = next(q for q in plan["quarters"] if q["key"] == quarter_key)
        lines = [f"**{row['code']} — {row['title']}** sits in "
                 f"**{quarter['label']}** ({row['units']} units)."]
        if row.get("reasons"):
            lines += [""] + [f"- {reason}" for reason in row["reasons"]]
        if row.get("cautions"):
            lines += [""] + [f"⚠️ {caution}" for caution in row["cautions"]]
        if row.get("swappable"):
            lines += ["", "Say the word and I'll show what else fits that slot."]
        else:
            lines += ["", "This one is required — there is nothing to choose here."]
        return BotReply("\n".join(lines), [], "plan")
    return None


SMALL_TALK_SYSTEM = (
    "You are THRIVE, a Rady MSBA course planner. The student already has a "
    "finished plan of study and has just said something that is not a request "
    "to change it. Reply in AT MOST two sentences. Be warm and brief. Do NOT "
    "restate the plan or list any courses. If they asked something that is not "
    "about their courses or this programme at all, say plainly that it is "
    "outside what you do -- you recommend electives and build plans of study -- "
    "and do not send them to MSBA advising for it, because advising cannot "
    "answer it either. If it is about the programme but not about the plan, "
    "point them at Ask THRIVE's Resources tab or MSBA advising via the "
    "Appointments tab. If it helps, remind them they can ask to swap a course, "
    "walk through the plan a quarter at a time, or see it again.")


def _small_talk_reply(llm, user, answers, question, asking):
    """Anything else, once a plan exists: answer briefly, never reprint.

    The fallthrough used to be `_plan_reply`, so every unrecognised message --
    including "ok" and "thanks!" -- reprinted the entire plan of study.
    """
    try:
        body = (llm.chat(SMALL_TALK_SYSTEM,
                         [{"role": "user", "content": question}]) or "").strip()
    except Exception:
        body = ""
    if not body:
        body = ("Your plan is set. You can ask me to swap a course, walk "
                "through it a quarter at a time, or show it again.")
    return BotReply(body, [], "plan")
