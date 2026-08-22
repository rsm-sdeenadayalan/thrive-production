"""Course-request prefill: the student record snapshot frozen onto each request."""
from rsm_thrive.models import Enrollment
from rsm_thrive.services.degree import degree_progress


def build_prefill(profile) -> dict:
    enrollments = (Enrollment.objects.filter(user=profile.user)
                   .select_related("course").order_by("course__code"))
    degree = degree_progress(profile)  # raises NotConfigured when unseeded
    return {
        "studentName": profile.display_name,
        "program": profile.program,
        "track": profile.track,
        "term": profile.current_term,
        "currentCourses": [f"{e.course.code} · {e.course.title}" for e in enrollments],
        "currentUnits": sum(e.course.units for e in enrollments),
        "unitsCompleted": degree["unitsCompleted"],
        "unitsRequired": degree["unitsRequired"],
    }
