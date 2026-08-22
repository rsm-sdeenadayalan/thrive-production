from django.utils import timezone

from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import Enrollment, Syllabus
from rsm_thrive.serializers.academic import course_payload, syllabus_payload


@api_login_required
def courses(request):
    now = timezone.now()
    enrollments = (
        Enrollment.objects.filter(user=request.user)
        .select_related("course", "course__syllabus")
        .prefetch_related("course__meetings", "course__assignments")
        .order_by("course__code")
    )
    return json_ok([course_payload(e.course, e, now) for e in enrollments])


@api_login_required
def syllabi(request):
    course_ids = Enrollment.objects.filter(user=request.user).values_list("course_id", flat=True)
    rows = Syllabus.objects.filter(course_id__in=course_ids).order_by("course__code")
    return json_ok([syllabus_payload(s) for s in rows])
