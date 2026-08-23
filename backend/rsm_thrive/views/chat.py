import logging
import time

from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from rsm_thrive.http import (BadRequest, api_login_required, json_error,
                             json_ok, parse_body)
from rsm_thrive.models import ChatMessage, ChatTurnLog, Conversation
from rsm_thrive.serializers.chat import conversation_payload
from rsm_thrive.services.bots import BotReply, answer_career, answer_electives, answer_faq
from rsm_thrive.services.llm import get_llm

logger = logging.getLogger("rsm_thrive.chat")

VALID_DESTINATIONS = {"resources", "courses", "career"}
MAX_BODY = 4000
DEGRADED_REPLY = ("I'm having trouble reaching my knowledge sources right "
                  "now. Your message is saved — try asking again in a minute.")

# Module-level seam: tests monkeypatch this with a FakeLLM factory.
llm_factory = get_llm


def _validated_body(body):
    text = body.get("body")
    if not isinstance(text, str) or not text.strip():
        raise BadRequest("body must be a non-empty string.")
    text = text.strip()
    if len(text) > MAX_BODY:
        raise BadRequest(f"body must be at most {MAX_BODY} characters.")
    return text


def _history_of(conversation):
    return [
        {"role": "user" if m.role == "student" else "assistant", "content": m.body}
        for m in conversation.messages.all()
    ]


def _run_bot(user, destination, question, history):
    started = time.monotonic()
    try:
        llm = llm_factory()
        if destination == "courses":
            reply = answer_electives(llm, user, question, history)
        elif destination == "career":
            reply = answer_career(llm, question, history)
        else:
            reply = answer_faq(llm, question, history)
    except Exception:
        logger.exception("bot turn failed (conversation=%s, destination=%s)",
                         getattr(user, "pk", None), destination)
        reply = BotReply(DEGRADED_REPLY, [], "degraded")
    duration_ms = int((time.monotonic() - started) * 1000)
    return reply, duration_ms


def _append_turn(conversation, destination, question):
    """Student turn -> bot (no transaction) -> thrive turn + log + bump.

    Two transactions, not one: the bot call does network work, and holding a
    DB transaction open across it is wrong. The student's message must also
    survive a bot crash, so it is committed before the bot ever runs.
    """
    history = _history_of(conversation)
    with transaction.atomic():
        ChatMessage.objects.create(conversation=conversation, role="student",
                                   body=question)

    reply, duration_ms = _run_bot(conversation.user, destination, question, history)

    with transaction.atomic():
        assistant = ChatMessage.objects.create(conversation=conversation,
                                               role="thrive", body=reply.body)
        ChatTurnLog.objects.create(message=assistant, bot=destination,
                                   model_note=reply.model_note,
                                   chunk_ids=reply.chunk_ids,
                                   duration_ms=duration_ms)
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["updated_at"])


@api_login_required
@require_http_methods(["GET", "POST"])
def conversations(request):
    if request.method == "GET":
        rows = (Conversation.objects.filter(user=request.user)
                .prefetch_related("messages").order_by("-updated_at", "-pk"))
        return json_ok([conversation_payload(c) for c in rows])
    try:
        body = parse_body(request)
        destination = body.get("destination")
        if destination not in VALID_DESTINATIONS:
            raise BadRequest(
                f"destination must be one of {sorted(VALID_DESTINATIONS)}.")
        question = _validated_body(body)
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    conversation_row = Conversation.objects.create(
        user=request.user, destination=destination, title=question[:60])
    _append_turn(conversation_row, destination, question)
    conversation_row = (Conversation.objects.filter(pk=conversation_row.pk)
                        .prefetch_related("messages").first())
    return json_ok(conversation_payload(conversation_row), status=201)


def _own_conversation(user, conversation_id):
    if not conversation_id.startswith("conv-"):
        return None
    pk = conversation_id.removeprefix("conv-")
    if not (pk.isascii() and pk.isdigit()):
        return None
    return (Conversation.objects.filter(pk=pk, user=user)
            .prefetch_related("messages").first())


@api_login_required
def conversation(request, conversation_id):
    row = _own_conversation(request.user, conversation_id)
    if row is None:
        return json_error("unknown_conversation",
                          f"No conversation {conversation_id}.", 404)
    return json_ok(conversation_payload(row))


@api_login_required
@require_http_methods(["POST"])
def conversation_messages(request, conversation_id):
    row = _own_conversation(request.user, conversation_id)
    if row is None:
        return json_error("unknown_conversation",
                          f"No conversation {conversation_id}.", 404)
    try:
        question = _validated_body(parse_body(request))
    except BadRequest as exc:
        return json_error("bad_request", str(exc), 400)
    _append_turn(row, row.destination, question)
    row = (Conversation.objects.filter(pk=row.pk)
           .prefetch_related("messages").first())
    return json_ok(conversation_payload(row))
