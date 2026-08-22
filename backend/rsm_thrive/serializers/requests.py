from rsm_thrive.serialize import iso_instant


def request_payload(req) -> dict:
    return {
        "id": f"req-{req.pk}",
        "type": req.type,
        "course": req.course,
        "reason": req.reason,
        "status": req.status,
        "submittedAt": iso_instant(req.submitted_at) if req.submitted_at else None,
        "prefill": req.prefill,
    }
