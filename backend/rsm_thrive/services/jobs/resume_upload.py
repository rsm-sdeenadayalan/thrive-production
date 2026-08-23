"""LLM extraction of a structured resume profile from raw uploaded resume text."""

from rsm_thrive.services.llm import parse_llm_json

EXTRACT_PROMPT = (
    "Extract a structured resume profile from this resume text. Reply with "
    "JSON only: {\"summary\": \"<2-3 sentence professional summary in the "
    "candidate's voice>\", \"skills\": [<skill names>], \"experience\": "
    "[{\"title\": ..., \"organization\": ..., \"period\": ..., \"bullets\": "
    "[<achievement strings>]}]}. Use only information present in the text."
)


class UploadError(Exception):
    """The LLM produced output that cannot be trusted as a resume profile."""


def _sanitize_skills(skills):
    seen = set()
    out = []
    for skill in skills or []:
        if not isinstance(skill, str):
            continue
        name = skill.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _sanitize_experience(experience):
    out = []
    for entry in experience or []:
        if not isinstance(entry, dict):
            continue
        bullets = [b.strip() for b in entry.get("bullets") or []
                  if isinstance(b, str) and b.strip()]
        out.append({
            "title": str(entry.get("title") or ""),
            "organization": str(entry.get("organization") or ""),
            "period": str(entry.get("period") or ""),
            "bullets": bullets,
        })
    return out


def extract_profile(llm, text: str) -> dict:
    raw = llm.chat(EXTRACT_PROMPT, [{"role": "user", "content": text}],
                   json_mode=True)
    envelope = parse_llm_json(raw)

    summary = envelope.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise UploadError("summary is missing or empty.")

    return {
        "summary": summary.strip(),
        "skills": _sanitize_skills(envelope.get("skills")),
        "experience": _sanitize_experience(envelope.get("experience")),
    }
