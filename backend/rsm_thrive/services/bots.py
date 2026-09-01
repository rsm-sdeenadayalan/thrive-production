"""The three destination bots. Pure functions over (llm, question, history)."""

import re
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
        # Deterministic refusal: no context means no answer, and no LLM call
        # means the refusal cannot be argued with. Spec §5's binding rule.
        return BotReply(config["refusal_reply"], [], "refusal")
    system = f"{config['system_prompt']}\n\nContext passages:\n\n{build_context(hits)}"
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    body = llm.chat(system, messages)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "llm")


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


ASIDE_SYSTEM = (
    "You are THRIVE, the Rady MSBA course planner, answering a student's "
    "question about courses while a short planning interview is in progress. "
    "Answer ONLY from the catalog entries below — they are the whole of what "
    "this programme offers. Be concrete and brief, at most four sentences or a "
    "short list. Name courses by code. Where the entry gives units, the quarters "
    "it runs in, prerequisites or tools, use them; where it does not, say the "
    "catalog does not list that rather than guessing. Never invent a course, a "
    "unit count, a prerequisite or a term. Do not ask a question back — the "
    "interview's next question is appended for you.")

# Said for anything that is not about courses. This bot plans a plan of study;
# it is not the FAQ bot and should not answer as though it were.
ASIDE_UNKNOWN = (
    "That's outside what I do — I'm the course planner, so I can answer "
    "questions about MSBA courses and electives and build your plan of study. "
    "For anything "
    "else about the programme, Ask THRIVE's **Resources** tab answers from "
    "Rady's own material, and MSBA advising is bookable from the "
    "**Appointments** tab.")


_TRAILING_MARKUP = re.compile(r"[\s*_`~]+$")


def _without_trailing_question(body):
    """Drop a question the aside ended on, because the step follows it.

    The prompt says not to ask one back. The model does anyway -- asked "are
    you an AI?" it answered, then added "which quarter are you currently in?",
    which landed directly above the interview's own different question and gave
    the student two things to answer. Prompt text is not a control; removing it
    afterwards is.

    Only TRAILING questions go. One in the middle of an explanation ("what does
    that mean for you? it means...") is part of the answer.
    """
    text = (body or "").strip()
    while text:
        # Test against a copy with trailing emphasis removed -- the question
        # arrives bolded ("**which quarter are you in?**") often enough that a
        # bare endswith("?") misses it -- but keep the original as the result,
        # so legitimate trailing bold is not stripped off an answer.
        probe = _TRAILING_MARKUP.sub("", text)
        if not probe.endswith("?"):
            break
        cut = max(probe.rfind(". "), probe.rfind("! "), probe.rfind("\n"))
        if cut < 0:
            return ""          # the whole aside was a question
        text = text[:cut + 1].strip()
    return text


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


def _aside(llm, question):
    """Answer a question about courses, then let the interview step be re-asked.

    Every question used to get the current step repeated back verbatim, byte for
    byte, so a student who asked anything got no answer and no sign that asking
    was pointless. This answers the ones this bot can actually answer and says
    so plainly for the rest.

    Returns (prefix, chunk_ids). The prefix ends in a rule so the step below it
    still reads as the question being asked rather than as more prose.
    """
    context = _catalog_context(question)
    if context is None:
        # Not a course question. No LLM call at all -- the refusal is a fact
        # about scope, not a judgement to be talked out of.
        return f"{ASIDE_UNKNOWN}\n\n---\n\n", []
    try:
        system = f"{ASIDE_SYSTEM}\n\nCatalog entries:\n\n{context}"
        body = (llm.chat(system, [{"role": "user", "content": question}]) or "").strip()
    except Exception:
        # An aside is a courtesy. If it fails the interview must still run, but
        # it must not vanish either -- a silent failure is indistinguishable
        # from the bug this path exists to fix.
        return f"{ASIDE_UNKNOWN}\n\n---\n\n", []
    body = _without_trailing_question(body)
    return f"{body or ASIDE_UNKNOWN}\n\n---\n\n", []


CLARIFY_FALLBACK = ("What role are you aiming for after the program? Say "
                    "something like 'data scientist' or 'product manager' "
                    "and I can be specific.")
ALL_COVERED = ("Based on your enrollments you've already covered the "
               "electives that fit that goal best — come chat with academic "
               "advising about what's next.")


def _extract_intake(llm, config, history, question):
    """Pull the student's stated answers out of what they have typed.

    The student's OWN turns only, handed over as a labelled list inside one user
    message rather than replayed as a chat history. Both details are load-bearing
    and both were learned the hard way.

    Replaying the history as a conversation put the model back in the role of
    the interviewer: given its own "Which track are you on?" followed by the
    student's "17 month", it answered with "Great, you're on the 17-month track!
    Step 2 of 4..." instead of returning JSON. `parse_llm_json` wrapped that
    prose as a reply, extraction produced nothing, and the interview asked the
    same question forever. Framing the input as data to read rather than a
    conversation to continue is what stops that.

    Dropping the assistant turns also loses nothing: the questions contain no
    information about what the STUDENT said, and they are what invited the
    model to keep talking.
    """
    system = config["intake_extract_prompt"]
    for key, value in planner.intake_extract_placeholders().items():
        # `.replace`, not `.format`: the prompt contains literal JSON braces.
        system = system.replace("{" + key + "}", value)
    said = [turn["content"] for turn in history if turn.get("role") == "user"]
    said.append(question)
    transcript = "\n".join(f"- {line}" for line in said if line)
    payload = ("Everything the student has said so far, oldest first:\n"
               f"{transcript}\n\nReturn only the JSON object described above.")
    raw = parse_llm_json(
        llm.chat(system, [{"role": "user", "content": payload}], json_mode=True))
    return planner.normalise_intake(raw), planner.unmatched_goal_of(raw)


def _divergence_note(answers, plan):
    """What a student on a fixed route has dropped out of their bundle.

    The design document is explicit that a recommendation which does not say
    what it gives up is not a recommendation. On a fixed route the bundle IS
    the recommendation, so swapping an anchor course out is exactly the moment
    to say so -- once, plainly, without refusing the swap.
    """
    from rsm_thrive.services import bundles

    if planner.route_of(answers) != "fixed":
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


def _plan_reply(user, answers):
    planner.save_intake(user, answers)
    plan = planner.build_for(answers, planner.taken_course_ids(user))
    body = planner.render_plan_markdown(plan) + _divergence_note(answers, plan)
    body += ("\n\nWant to go through it a quarter at a time? I'll show what "
             "else fits each elective slot and what each one teaches, so you "
             "can swap before you finalise.")
    return BotReply(body, [], "plan", planner.review_intro_replies(answers))


def _review_reply(conversation, user, answers, index):
    """Show one quarter of the review and remember where we are."""
    taken = planner.taken_course_ids(user)
    record = planner.save_intake(user, answers)
    plan = planner.build_for(answers, taken, record.selections)
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


def _retitle_if_button_pressed(conversation, answers):
    """Give a plan conversation a title that says what it is about.

    A conversation is titled from the student's FIRST message, which works
    everywhere a student opens by typing a question. It does not work here: the
    course recommender opens by asking "Which track are you on?" with two
    buttons, so the first message is usually the word "17 month" — and the
    saved list filled with rows called "17 month", indistinguishable from each
    other and silent about what each plan was for.

    Only a title that IS one of those closed-set answers gets replaced. A
    student who opened by typing "which electives suit a product manager" wrote
    a better title than this function can compose, and it is left alone.
    """
    title = planner.conversation_title(answers)
    if not title or conversation.title == title:
        return
    if conversation.title.strip().lower() not in planner.interview_answers():
        return
    conversation.title = title[:60]
    conversation.save(update_fields=["title"])


def answer_electives(llm, conversation, question, history):
    """Interview the student, then build and maintain their plan of study.

    Replaces the previous one-shot behaviour, which extracted a career goal and
    returned five ranked electives. That answered a narrower question than
    students ask: it never established which track they were on, so it could
    not say WHEN to take anything, and a flat list of five courses is not a plan
    — a student still has to work out which quarter each one belongs in and what
    fills the other slots.

    The interview is scoped to THIS conversation. A new chat starts the
    questions over, which is what makes the flow testable and what stops an
    answer given last week from quietly standing in for one the student has not
    been asked yet.
    """
    config = bot_config("electives")
    user = conversation.user
    # Merge onto this conversation's answers rather than trusting one extraction
    # to recover the whole chat. Measured live: asked "17 month" and then
    # "product manager", the extractor returned the goal and a null track, which
    # sent the student back to step one.
    asking = planner.is_question(question)
    extracted, unmatched = _extract_intake(
        llm, config, _trimmed(history, config), question)
    stored = planner.load_session_intake(conversation)
    answers = planner.merge_intake(stored, extracted, asking=asking)
    # Did this turn change an answer the plan is actually BUILT from? Once a
    # plan exists that is the difference between "rebuild and show it" and "say
    # something back": a student who changed their mind wants the new plan, a
    # student who said "thanks!" does not.
    #
    # Compared field by field over the interview's own questions rather than
    # `answers != stored`, because that compared the whole dict -- so the
    # extractor quietly adding an `interests` tag counted as a change and
    # reprinted the entire plan of study. Measured on "do you have access to cs
    # classes?", which reprinted 3,700 characters at a yes/no question.
    # `workload` is included even though it is no longer a step of its own: the
    # load question replaced it, but an extractor still reports the word and a
    # student answering it has changed their plan. Without it, "moderate" on the
    # last turn of the interview taught the interview something and was then
    # treated as small talk, so the plan it completed was never shown.
    _shaping = [f for step in planner.INTAKE_STEPS for f in step["fields"]]
    _shaping.append("workload")
    changed_answers = any(stored.get(field) != answers.get(field)
                          for field in _shaping)
    planner.save_session_intake(conversation, answers)
    _retitle_if_button_pressed(conversation, answers)

    step = planner.next_intake_step(answers)
    if step:
        # If this step has already been asked twice and is still unanswered,
        # assume the blanks rather than asking a fourth time. Only the skill
        # areas are assumable: a track or a career goal must come from the
        # student, so those keep asking.
        # `in`, not `startswith`: a step asked after a question now carries the
        # answer to that question above it, so the marker is no longer the first
        # thing in the body. With `startswith` the count stayed at zero, the
        # escape hatch below never fired, and a student who asked anything
        # during the skills step could be asked for them forever.
        marker = f"**Step {planner.step_position(step)} of"
        asked = sum(1 for turn in history
                    if turn.get("role") == "assistant"
                    and marker in turn.get("content", ""))
        # A career the catalog does not serve is answered, not re-prompted with
        # a menu of ten roles the student did not ask about.
        # A turn that taught the interview nothing is not a career statement.
        # `asking` alone was not enough: "how do i set up zoom" carries no
        # question mark, so the strict test said no, the extractor reported it
        # as an unmatched goal, and the student was told their career was not
        # covered -- an answer to a question they never asked. This is the same
        # condition the aside uses, and the two must agree: a turn cannot be
        # both "a career we do not serve" and "a question to answer".
        wants_aside = asking or not changed_answers
        # `is_course_question` rather than `wants_aside`: an uncovered career
        # teaches the interview nothing, so it looks exactly like a question by
        # that test and "esports analyst" was being answered with the scope
        # refusal. What separates them is vocabulary -- a career statement does
        # not use the words of the catalog -- and past that cheap check the
        # role lookup itself decides, returning nothing for input that is not a
        # job at all.
        from rsm_thrive.services import electives as _electives

        # Industry questions need one bounded web lookup for current skill
        # requirements. The new segment never lets web output name courses:
        # it intersects the returned requirements with the local catalog and
        # renders only courses that meet the deterministic match threshold.
        if step["key"] == "goals" and _electives.is_course_question(question):
            from rsm_thrive.services.grounded_course_advisor import (
                recommend_for_question,
            )

            industry_reply, _matched_codes = recommend_for_question(llm, question)
            if industry_reply:
                return BotReply(
                    f"{industry_reply}\n\n---\n\n"
                    + planner.render_question(step, answers),
                    [], "industry-catalog", planner.quick_replies_for(step),
                    planner.rating_form_for(step, answers),
                )

        if (step["key"] == "goals" and unmatched and not answers.get("goals")
                and not _electives.is_course_question(question)):
            # A career with no prepared bundle is not a career this catalog
            # cannot serve. Look up what the job actually needs -- on the web,
            # so a role that appeared last year is described from what
            # employers ask for now -- and match that against the courses we
            # really have. Only if nothing matches do we fall back to asking
            # them to pick from the covered list, which is the honest answer
            # when it is the true one.
            from rsm_thrive.services import role_lookup

            role = role_lookup.skills_for_role(llm, unmatched)
            if role:
                matches = role_lookup.courses_for_role(role)
                found = role_lookup.explain_fit(llm, role, matches) if matches else ""
                if found:
                    return BotReply(
                        f"{found}\n\n---\n\n"
                        + planner.render_question(step, answers),
                        [], "intake", planner.quick_replies_for(step),
                        planner.rating_form_for(step, answers))
                # A real job the catalog genuinely cannot serve. Asking them to
                # pick a covered role is the honest answer HERE and only here.
                return BotReply(planner.uncovered_career_reply(unmatched), [],
                                "no-track")
            # Not a job at all -- "how do i set up zoom" was reaching this
            # branch and being told its career was not covered. Falling through
            # lets the aside answer it, or say plainly that it is out of scope.
            #
            # Clearing `unmatched` matters as much as falling through: it is
            # what `render_question` uses to open with "I don't have a track
            # built around ...", which is a sentence about a CAREER. Left set,
            # the step still described a Zoom question as an uncovered one.
            unmatched = ""

        filled, assumed = planner.fill_assumed_skills(answers, step["missing"])
        if assumed and asked >= planner.MAX_STEP_ATTEMPTS:
            answers = filled
            planner.save_session_intake(conversation, answers)
            step = planner.next_intake_step(answers)
            if step:
                aside, cited = _aside(llm, question) if wants_aside else ("", [])
                return BotReply(aside + planner.render_question(step, answers, unmatched),
                                cited, "intake", planner.quick_replies_for(step),
                                planner.rating_form_for(step, answers))
            reply = _plan_reply(user, answers)
            return BotReply(
                "I've assumed **some exposure** for "
                + ", ".join(assumed)
                + " since we hadn't settled those — say the word and I'll redo "
                  "the plan with different levels.\n\n" + reply.body,
                [], "plan")
        # A question gets answered before the step is put again. See `_aside`.
        #
        # `asking` is the strict test, because its other job is refusing to
        # overwrite a stored answer and a false positive there loses a real
        # one. For an aside the risk runs the other way, so a turn that taught
        # the interview NOTHING NEW counts too -- it was not an answer, whatever
        # its punctuation. That is what reaches "tell me about parking permits"
        # and "What classes do you have access to", neither of which ends in a
        # question mark.
        #
        # `changed_answers`, not `not extracted`: the extractor is handed the
        # whole transcript every turn and dutifully re-reports what the student
        # already said, so `extracted` is almost never empty. Measured live --
        # asked "What classes do you have access to" at the goals step, it
        # returned {"track": "11 month"} from three turns earlier, the aside was
        # skipped, and the student got the same step repeated with no answer.
        aside, cited = _aside(llm, question) if wants_aside else ("", [])
        return BotReply(
            aside + planner.render_question(step, answers, unmatched), cited,
            "intake", planner.quick_replies_for(step),
            planner.rating_form_for(step, answers))

    # A targeted industry question remains answerable after the plan exists.
    # Keep the same strict web-to-catalog boundary used during intake.
    if step is None:
        from rsm_thrive.services.grounded_course_advisor import recommend_for_question

        industry_reply, _matched_codes = recommend_for_question(llm, question)
        if industry_reply:
            return BotReply(industry_reply, [], "industry-catalog")

    # Switching how the electives are filled. Checked before everything else
    # once a plan exists: it is a rebuild request, and the words carry no course
    # code so the change handler would otherwise ignore them and the fallthrough
    # would reprint the plan unchanged.
    wanted_route = planner.route_intent(question)
    if wanted_route and planner.next_intake_step(answers) is None:
        answers = {**answers, "route": wanted_route}
        planner.save_session_intake(conversation, answers)
        reply = _plan_reply(user, answers)
        lead = ("Here it is built from the recommended bundle for that path."
                if wanted_route == "fixed"
                else "Here it is filled against your own skills and workload "
                     "instead.")
        return BotReply(f"{lead}\n\n{reply.body}", [], "plan",
                        reply.quick_replies)

    # The guided walk-through, once a plan exists. Checked before the change
    # handler because "next quarter" names no course and would otherwise fall
    # through to rebuilding the plan from scratch.
    session = planner.load_session_review(conversation)
    intent = planner.review_intent(question)
    if intent == "finalise":
        return _finalise_reply(conversation, user, answers)
    if intent == "start":
        return _review_reply(conversation, user, answers, 0)
    if intent == "next" and session is not None:
        return _review_reply(conversation, user, answers, session["index"] + 1)

    # A question ABOUT a course in the plan is answered, not acted on. Checked
    # before the change handler because that handler dispatches on any course
    # code it finds, so "why did you pick MGTA 461?" came back as a menu of
    # alternatives -- a swap UI in answer to a question about the reasoning.
    if asking:
        explained = _explain_course(user, answers, question)
        if explained is not None:
            return explained

    change = _handle_change_request(user, answers, question)
    if change is not None:
        # Mid-review, a swap should hand back the quarter it happened in rather
        # than the whole plan: the student is looking at one quarter, and
        # replacing their view with twelve courses loses their place.
        if session is not None:
            return _review_reply(conversation, user, answers, session["index"])
        return change

    # Reprint only when the student asked for the plan. This used to be the
    # unconditional fallthrough, so "thanks!", "ok", "hmm", "how do I enrol?"
    # and every unrecognised message reprinted the whole plan of study --
    # measured at 3,680 characters, 24 times out of 25 probes.
    if _wants_the_plan(question) or planner.next_intake_step(answers) is None and changed_answers:
        return _plan_reply(user, answers)
    return _small_talk_reply(llm, user, answers, question, asking)
