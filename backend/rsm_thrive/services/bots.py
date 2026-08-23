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


def build_context(hits):
    lines = []
    for n, (chunk, _score) in enumerate(hits, start=1):
        title = chunk.document.title
        head = f"[{n}] {title} — {chunk.heading}" if chunk.heading else f"[{n}] {title}"
        lines.append(f"{head}\n{chunk.text}")
    return "\n\n".join(lines)


def append_sources(body, hits):
    if not hits:
        return body
    titles = []
    for chunk, _score in hits:
        if chunk.document.title not in titles:
            titles.append(chunk.document.title)
    return f"{body}\n\nSources: {', '.join(titles)}"


def _trimmed(history, config):
    return history[-config["max_history_turns"]:]


def answer_faq(llm, question, history):
    config = bot_config("faq")
    hits = retrieve(question, "resources", config["top_k"], config["min_similarity"])
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
        return BotReply(envelope.get("reply") or CLARIFY_FALLBACK, [], "clarify")

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
