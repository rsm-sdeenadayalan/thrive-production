from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.serializers.students import student_payload


@api_login_required
def me(request):
    return json_ok(student_payload(request.user.thrive_profile))
