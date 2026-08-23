from rsm_thrive.http import api_login_required, json_ok, profile_required
from rsm_thrive.serializers.students import student_payload


@api_login_required
@profile_required
def me(request):
    return json_ok(student_payload(request.thrive_profile))
