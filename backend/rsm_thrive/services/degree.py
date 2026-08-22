from rsm_thrive.models import DegreeGap, DegreeRequirement, Enrollment, ProgramPhaseRow
from rsm_thrive.serialize import iso_date


class NotConfigured(Exception):
    """Raised when required seed data is missing for a student's track."""
    pass


def _phase_status(phase, today):
    if phase.end < today:
        return "complete"
    if phase.start <= today:
        return "current"
    return "upcoming"


def program_timeline(profile, today) -> dict:
    rows = list(ProgramPhaseRow.objects.filter(track=profile.track))
    required = [p for p in rows if not p.optional]
    if not required:
        raise NotConfigured(f"No program phases configured for track {profile.track!r}.")
    program_end = max(p.end for p in required)
    finish_term = max(required, key=lambda p: p.end).term
    span = (program_end - profile.program_start).days or 1
    pct = round(100 * (today - profile.program_start).days / span)
    current = next((p for p in rows if _phase_status(p, today) == "current"), None)
    return {
        "phases": [{
            "id": p.phase_id, "label": p.label, "term": p.term,
            "start": iso_date(p.start), "end": iso_date(p.end),
            "optional": p.optional, "status": _phase_status(p, today),
        } for p in rows],
        "currentPhaseId": current.phase_id if current else None,
        "percentComplete": max(0, min(100, pct)),
        "programStart": iso_date(profile.program_start),
        "programEnd": iso_date(program_end),
        "expectedFinishTerm": finish_term,
        "track": profile.track,
    }


def degree_progress(profile) -> dict:
    try:
        req = DegreeRequirement.objects.get(track=profile.track)
    except DegreeRequirement.DoesNotExist:
        raise NotConfigured(f"No degree requirements configured for track {profile.track!r}.")
    completed = (Enrollment.objects.filter(user=profile.user, completed=True)
                 .select_related("course"))
    return {
        "unitsCompleted": sum(e.course.units for e in completed),
        "unitsRequired": req.units_required,
        "coreDone": sum(1 for e in completed if e.bucket == "core"),
        "coreRequired": req.core_required,
        "electiveDone": sum(1 for e in completed if e.bucket == "elective"),
        "electiveRequired": req.elective_required,
        "gaps": [{
            "id": f"gap-{g.pk}", "label": g.label, "detail": g.detail,
            "severity": g.severity,
        } for g in DegreeGap.objects.filter(user=profile.user).order_by("pk")],
        "track": profile.track,
    }
