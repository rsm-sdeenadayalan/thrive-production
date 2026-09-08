from rsm_thrive.serialize import iso_instant


def _feedback_of(message):
    """The student's own verdict on this reply, so a reload shows it back.

    A thumb that vanishes on refresh reads as one that was not recorded, and a
    tester who thinks their click was lost either clicks again or stops
    clicking. Read through `turn_log` because that is where the verdict lives:
    a rating is only worth anything beside the trace that produced it. See
    `models.chat.TurnFeedback`.
    """
    turn = getattr(message, "turn_log", None)
    if turn is None:
        return None
    feedback = getattr(turn, "feedback", None)
    if feedback is None:
        return None
    return {"rating": feedback.rating, "note": feedback.note}


def conversation_payload(conversation) -> dict:
    return {
        "id": f"conv-{conversation.pk}",
        "destination": conversation.destination,
        "title": conversation.title,
        "messages": [
            {
                "id": f"msg-{message.pk}",
                "role": message.role,
                "body": message.body,
                "quickReplies": message.quick_replies or [],
                "form": message.form,
                "sentAt": iso_instant(message.sent_at),
                # Null on student turns and on replies written before the turn
                # log existed. Present-and-null means "rateable, not yet rated".
                "feedback": _feedback_of(message),
                "rateable": getattr(message, "turn_log", None) is not None,
            }
            for message in conversation.messages.all()
        ],
        "updatedAt": iso_instant(conversation.updated_at),
    }
