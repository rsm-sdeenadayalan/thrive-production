"""The three destination bots. Pure functions over (llm, question, history)."""

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


def _plan_reply(user, answers):
    planner.save_intake(user, answers)
    plan = planner.build_plan(answers, planner.taken_course_ids(user))
    body = planner.render_plan_markdown(plan)
    body += ("\n\nWant to go through it a quarter at a time? I'll show what "
             "else fits each elective slot and what each one teaches, so you "
             "can swap before you finalise.")
    return BotReply(body, [], "plan", planner.review_intro_replies())


def _review_reply(conversation, user, answers, index):
    """Show one quarter of the review and remember where we are."""
    taken = planner.taken_course_ids(user)
    record = planner.save_intake(user, answers)
    plan = planner.build_plan(answers, taken, record.selections)
    body, replies, _last = planner.review_quarter(plan, answers, index, taken)
    session = planner.save_session_intake(conversation, answers)
    session.review = {"index": index}
    session.save(update_fields=["review", "updated_at"])
    return BotReply(body, [], "review", replies)


def _finalise_reply(conversation, user, answers):
    taken = planner.taken_course_ids(user)
    record = planner.save_intake(user, answers)
    plan = planner.build_plan(answers, taken, record.selections)
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
    plan = planner.build_plan(answers, planner.taken_course_ids(user),
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
        updated = planner.build_plan(answers, planner.taken_course_ids(user),
                                     record.selections)
        return BotReply(
            f"Swapped **{row['code']}** for **{replacement}**.\n\n"
            + planner.render_plan_markdown(updated), [], "plan")

    return BotReply(planner.render_alternatives_markdown(
        planner.alternatives_for(plan, answers, quarter_key, slot,
                                 planner.taken_course_ids(user))), [], "plan")


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
    extracted, unmatched = _extract_intake(
        llm, config, _trimmed(history, config), question)
    answers = planner.merge_intake(
        planner.load_session_intake(conversation), extracted)
    planner.save_session_intake(conversation, answers)

    step = planner.next_intake_step(answers)
    if step:
        # If this step has already been asked twice and is still unanswered,
        # assume the blanks rather than asking a fourth time. Only the skill
        # areas are assumable: a track or a career goal must come from the
        # student, so those keep asking.
        asked = sum(1 for turn in history
                    if turn.get("role") == "assistant"
                    and turn.get("content", "").startswith(
                        f"**Step {planner.step_position(step)} of"))
        # A career the catalog does not serve is answered, not re-prompted with
        # a menu of ten roles the student did not ask about.
        if step["key"] == "goals" and unmatched and not answers.get("goals"):
            return BotReply(planner.uncovered_career_reply(unmatched), [],
                            "no-track")

        filled, assumed = planner.fill_assumed_skills(answers, step["missing"])
        if assumed and asked >= planner.MAX_STEP_ATTEMPTS:
            answers = filled
            planner.save_session_intake(conversation, answers)
            step = planner.next_intake_step(answers)
            if step:
                return BotReply(planner.render_question(step, answers, unmatched),
                                [], "intake", planner.quick_replies_for(step),
                                planner.rating_form_for(step))
            reply = _plan_reply(user, answers)
            return BotReply(
                "I've assumed **some exposure** for "
                + ", ".join(assumed)
                + " since we hadn't settled those — say the word and I'll redo "
                  "the plan with different levels.\n\n" + reply.body,
                [], "plan")
        return BotReply(
            planner.render_question(step, answers, unmatched), [], "intake",
            planner.quick_replies_for(step), planner.rating_form_for(step))

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

    change = _handle_change_request(user, answers, question)
    if change is not None:
        # Mid-review, a swap should hand back the quarter it happened in rather
        # than the whole plan: the student is looking at one quarter, and
        # replacing their view with twelve courses loses their place.
        if session is not None:
            return _review_reply(conversation, user, answers, session["index"])
        return change
    return _plan_reply(user, answers)
