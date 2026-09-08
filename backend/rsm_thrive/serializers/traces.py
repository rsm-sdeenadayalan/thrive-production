"""One assistant turn, rendered so a bad answer explains itself.

The shape is dictated by the question a tester's complaint raises: *why did it
say that?* Answering it needs the question, the reply, the route that was
chosen, and the exact passages the model was looking at — together, in one
object. Anything that has to be fetched separately to make sense of the rest
does not belong in a different call.

Chunk TEXT is opt-in (`with_chunks`). A listing of fifty turns at ten chunks
each is a few hundred kilobytes of prose nobody reads while scanning; the ids
are always there, and the text arrives when a trace is opened.
"""

from rsm_thrive.serialize import iso_instant


def _feedback_payload(turn):
    feedback = getattr(turn, "feedback", None)
    if feedback is None:
        return None
    return {
        "rating": feedback.rating,
        "note": feedback.note,
        "by": feedback.user.username,
        "at": iso_instant(feedback.updated_at),
    }


def _chunk_payload(chunk):
    return {
        "id": chunk.pk,
        "documentTitle": chunk.document.title,
        "documentKind": chunk.document.kind,
        "sourceUrl": chunk.document.source_url,
        "heading": chunk.heading,
        "text": chunk.text,
    }


def turn_payload(turn, chunks_by_id=None):
    """`chunks_by_id` present means "inline the text"; absent means ids only."""
    payload = {
        "id": f"turn-{turn.pk}",
        "createdAt": iso_instant(turn.created_at),
        "conversationId": f"conv-{turn.message.conversation_id}",
        "messageId": f"msg-{turn.message_id}",
        "student": turn.message.conversation.user.username,
        "bot": turn.bot,
        "route": turn.route,
        "routeConfidence": turn.route_confidence,
        "modelNote": turn.model_note,
        "refused": turn.refused,
        "durationMs": turn.duration_ms,
        "question": turn.question,
        "reply": turn.message.body,
        "chunkIds": list(turn.chunk_ids or []),
        "feedback": _feedback_payload(turn),
    }
    if chunks_by_id is not None:
        # Missing ids are reported rather than dropped. A chunk that has since
        # been re-ingested is exactly the case where "the answer came from
        # nowhere" is the finding, and silently returning four chunks where the
        # log says five hides it.
        payload["chunks"] = [
            chunks_by_id[cid] if cid in chunks_by_id
            else {"id": cid, "missing": True}
            for cid in (turn.chunk_ids or [])
        ]
    return payload
