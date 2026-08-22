from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import Assignment, Enrollment, StudentAssignment
from rsm_thrive.serializers.academic import assignment_payload


def _my_assignments(user):
    """Assignments of enrolled courses, due asc — the contract's guaranteed sort."""
    course_ids = Enrollment.objects.filter(user=user).values_list("course_id", flat=True)
    return Assignment.objects.filter(course_id__in=course_ids).order_by("due_date", "id")


@api_login_required
def assignments(request):
    rows = _my_assignments(request.user)
    statuses = {
        sa.assignment_id: sa
        for sa in StudentAssignment.objects.filter(user=request.user, assignment__in=rows)
    }
    return json_ok([assignment_payload(a, statuses.get(a.id)) for a in rows])
