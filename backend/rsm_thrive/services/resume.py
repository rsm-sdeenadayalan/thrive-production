"""Deterministic resume generation, ported from the frontend mock verbatim.
An LLM-written summary is a Phase C enhancement behind the same seam."""
from django.db import transaction

from rsm_thrive.models import Enrollment, ResumeCourseHighlight, ResumeVersion, Skill
from rsm_thrive.serializers.resume import skill_payload


def compose_summary(goal: str, program: str, skill_names: list[str]) -> str:
    headline = ", ".join(skill_names[:4])
    tail = (f", and {len(skill_names) - 4} more."
            if len(skill_names) > 4 else ".")
    return (f"{program} candidate at UC San Diego working toward a {goal} role. "
            f"Coursework and projects across {headline}{tail}")


def generate_version(profile):
    user = profile.user
    previous = ResumeVersion.objects.filter(user=user, is_current=True).first()

    skills = [skill_payload(s)
              for s in Skill.objects.filter(user=user).order_by("name", "pk")]
    enrolled_codes = set(
        Enrollment.objects.filter(user=user).values_list("course__code", flat=True))
    resume_courses = [
        {"code": h.code, "title": h.title, "highlight": h.highlight}
        for h in ResumeCourseHighlight.objects.filter(code__in=enrolled_codes)
                                              .order_by("code")
    ]
    summary = compose_summary(profile.goal, profile.program,
                              [s["name"] for s in skills])

    prev_skill_names = {s["name"] for s in (previous.skills if previous else [])}
    prev_codes = {c["code"] for c in (previous.courses if previous else [])}
    diff = {
        "addedSkills": [s["name"] for s in skills
                        if s["name"] not in prev_skill_names],
        "addedCourses": [f"{c['code']} · {c['title']}" for c in resume_courses
                         if c["code"] not in prev_codes],
        "summaryChanged": (previous.summary if previous else None) != summary,
    }
    with transaction.atomic():
        ResumeVersion.objects.filter(user=user, is_current=True).update(
            is_current=False)
        version = ResumeVersion.objects.create(
            user=user,
            label=f"Regenerated from {profile.current_term} courses",
            summary=summary,
            skills=skills,
            courses=resume_courses,
            experience=(previous.experience if previous else []),
            is_current=True,
        )
    return version, diff
