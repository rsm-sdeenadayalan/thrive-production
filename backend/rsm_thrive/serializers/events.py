from rsm_thrive.serialize import iso_instant


def event_payload(event, goal: str) -> dict:
    payload = {
        "id": event.id,
        "title": event.title,
        "type": event.type,
        "start": iso_instant(event.start),
        "location": event.location,
        "relevantToGoal": bool(goal) and goal.lower() in
                          [t.lower() for t in event.goal_tags],
    }
    if event.end:
        payload["end"] = iso_instant(event.end)
    if event.description:
        payload["description"] = event.description
    if event.register_url:
        payload["registerUrl"] = event.register_url
    return payload
