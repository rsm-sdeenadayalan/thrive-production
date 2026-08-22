from rsm_thrive.http import api_login_required, json_ok
from rsm_thrive.models import ResourceLink


@api_login_required
def resources(request):
    rows = ResourceLink.objects.order_by("category", "title")
    out = []
    for r in rows:
        item = {"id": r.id, "title": r.title, "description": r.description,
                "url": r.url, "category": r.category}
        if r.owner:
            item["owner"] = r.owner
        out.append(item)
    return json_ok(out)
