from rsm_thrive.serialize import iso_instant


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
            }
            for message in conversation.messages.all()
        ],
        "updatedAt": iso_instant(conversation.updated_at),
    }
