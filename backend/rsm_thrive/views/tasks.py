from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.services.tasks import assemble_tasks


@api_login_required
def tasks(request):
    return json_ok(assemble_tasks(request.user))
