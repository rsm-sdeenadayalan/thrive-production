"""A tester's thumb on one answer.

Written against the TURN LOG rather than the message, so a verdict arrives
attached to the route, the chunks and the latency that produced it. See
`models.chat.TurnFeedback`.

The click and the note are separate writes on purpose. A thumb is one tap and
is recorded the moment it happens; the "what was wrong?" box opens afterwards
and PATCHes the same row. Asking for the sentence first is how twenty testers
become three.
"""

from django.utils import timezone
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import (BadRequest, api_login_required, json_error,
                             json_ok, parse_body)
from rsm_thrive.models import ChatMessage, TurnFeedback

MAX_NOTE = 2000
RATINGS = {"up", "down"}


def _own_message(user, conversation_id, message_id):
    """The assistant message this feedback is about, if it is theirs to rate."""
    for prefix, value in (("conv-", conversation_id), ("msg-", message_id)):
        if not value.startswith(prefix) or not value.removeprefix(prefix).isdigit():
            return None
    return (ChatMessage.objects
            .select_related("turn_log", "conversation")
            .filter(pk=message_id.removeprefix("msg-"),
                    conversation_id=conversation_id.removeprefix("conv-"),
                    conversation__user=user,
                    role="thrive")
            .first())


def _payload(feedback):
    if feedback is None:
        return {"rating": None, "note": ""}
    return {"rating": feedback.rating, "note": feedback.note}


@api_login_required
@require_http_methods(["POST", "DELETE"])
def message_feedback(request, conversation_id, message_id):
    message = _own_message(request.user, conversation_id, message_id)
    if message is None:
        return json_error("unknown_message",
                          f"No THRIVE message {message_id} in {conversation_id}.",
                          404)
    turn = getattr(message, "turn_log", None)
    if turn is None:
        # A reply written before the turn log existed, or seeded by a fixture.
        # There is nothing to attach a verdict to, and inventing a log row here
        # would put a turn in the trace view that never ran.
        return json_error("no_turn_log",
                          "That reply has no turn log, so it can't be rated.", 409)

    if request.method == "DELETE":
        TurnFeedback.objects.filter(turn=turn).delete()
        return json_ok(_payload(None))

    try:
        body = parse_body(request)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)

    rating = body.get("rating")
    note = body.get("note")
    if rating is None and note is None:
        return json_error("bad_request", "Send a rating, a note, or both.", 400)
    # `rating not in RATINGS` alone raised TypeError on an unhashable value --
    # a JSON object where a string was expected turned a bad request into a
    # 500. The type check has to come first, and `True` is excluded explicitly
    # because `isinstance(True, int)` is not the trap here but `bool` being a
    # perfectly good dict key is.
    if rating is not None and (not isinstance(rating, str)
                               or rating not in RATINGS):
        return json_error("bad_request",
                          f"rating must be one of {sorted(RATINGS)}.", 400)
    if note is not None and not isinstance(note, str):
        return json_error("bad_request", "note must be a string.", 400)
    if isinstance(note, str) and len(note) > MAX_NOTE:
        return json_error("bad_request",
                          f"note must be at most {MAX_NOTE} characters.", 400)

    feedback = TurnFeedback.objects.filter(turn=turn).first()
    if feedback is None:
        if rating is None:
            # A note with no thumb is not a verdict — there is nothing to
            # count it as. The client always sends the rating first.
            return json_error("bad_request",
                              "Rate the answer before adding a note.", 400)
        feedback = TurnFeedback(turn=turn, user=request.user)
    if rating is not None:
        feedback.rating = rating
    if note is not None:
        feedback.note = note.strip()
    # Whoever last expressed the verdict owns it. In practice this is always
    # the conversation's own student, because `_own_message` filters on them.
    feedback.user = request.user
    feedback.updated_at = timezone.now()
    feedback.save()
    return json_ok(_payload(feedback))
