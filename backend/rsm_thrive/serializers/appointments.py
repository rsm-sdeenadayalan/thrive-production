from rsm_thrive.serialize import iso_instant


def advisor_payload(advisor) -> dict:
    payload = {
        "id": advisor.id,
        "name": advisor.name,
        "role": advisor.role,
        "service": advisor.service,
        "location": advisor.location,
    }
    if advisor.avatar_url:
        payload["avatar"] = advisor.avatar_url
    if advisor.blurb:
        payload["blurb"] = advisor.blurb
    return payload


def slot_payload(slot, available: bool) -> dict:
    return {
        "id": slot.id,
        "advisorId": slot.advisor_id,
        "start": iso_instant(slot.start),
        "end": iso_instant(slot.end),
        "mode": slot.mode,
        "available": available,
    }
