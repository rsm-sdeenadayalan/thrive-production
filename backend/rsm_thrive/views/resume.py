from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Skill
from rsm_thrive.serializers.resume import skill_payload, version_payload


@api_login_required
def skills(request):
    rows = Skill.objects.filter(user=request.user).order_by("name", "pk")
    return json_ok([skill_payload(s) for s in rows])
