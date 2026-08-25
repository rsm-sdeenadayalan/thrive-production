"""The three destination bots. Pure functions over (llm, question, history)."""

from dataclasses import dataclass, field

from rsm_thrive.services.bot_config import bot_config
from rsm_thrive.services.electives import load_careers, recommend_for
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


def answer_electives(llm, user, question, history):
    config = bot_config("electives")
    careers = load_careers()

    extract_system = config["extract_prompt"].replace(
        "{role_ids}", ", ".join(sorted(careers)))
    messages = _trimmed(history, config) + [{"role": "user", "content": question}]
    envelope = parse_llm_json(llm.chat(extract_system, messages, json_mode=True))

    roles = [r for r in (envelope.get("career_roles") or []) if r in careers]
    if not envelope.get("ready") or not roles:
        reply = envelope.get("reply")
        is_usable = isinstance(reply, str) and reply.strip()
        return BotReply(reply if is_usable else CLARIFY_FALLBACK, [], "clarify")

    interests = [i for i in (envelope.get("interests") or []) if isinstance(i, str)]
    ranked = recommend_for(user, roles, interests,
                           limit=config["max_recommendations"])
    if not ranked:
        return BotReply(ALL_COVERED, [], "engine")

    lines = []
    for n, entry in enumerate(ranked, start=1):
        course = entry["course"]
        reasons = "; ".join(entry["reasons"]) or "general fit"
        lines.append(f"{n}. {course['code']} {course['title']} — "
                     f"score {entry['score']:.1f} — reasons: {reasons}")
    engine_block = "Ranked recommendations (deterministic engine):\n" + "\n".join(lines)

    hits = retrieve(" ".join([e["course"]["code"] for e in ranked] + [question]),
                    "courses", config["top_k"], config["min_similarity"])
    explain_system = f"{config['explain_prompt']}\n\n{engine_block}"
    if hits:
        explain_system += f"\n\nContext passages:\n\n{build_context(hits)}"
    body = llm.chat(explain_system, messages)
    return BotReply(append_sources(body, hits),
                    [chunk.pk for chunk, _ in hits], "engine+llm")
