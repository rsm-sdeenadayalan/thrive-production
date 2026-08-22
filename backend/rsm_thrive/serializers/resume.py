from rsm_thrive.serialize import iso_instant


def skill_payload(skill) -> dict:
    payload = {"id": f"skill-{skill.pk}", "name": skill.name, "source": skill.source}
    if skill.course_id:
        payload["courseId"] = skill.course_id
    return payload


def version_payload(version) -> dict:
    return {
        "id": f"rv-{version.pk}",
        "label": version.label,
        "createdAt": iso_instant(version.created_at),
        "summary": version.summary,
        "skills": version.skills,
        "courses": version.courses,
        "experience": version.experience,
        "isCurrent": version.is_current,
    }
