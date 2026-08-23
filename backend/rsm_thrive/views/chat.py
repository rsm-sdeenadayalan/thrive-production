from rsm_thrive.http import api_login_required, json_error, json_ok
from rsm_thrive.models import Conversation
from rsm_thrive.serializers.chat import conversation_payload


@api_login_required
def conversations(request):
    rows = (Conversation.objects.filter(user=request.user)
            .prefetch_related("messages").order_by("-updated_at", "-pk"))
    return json_ok([conversation_payload(c) for c in rows])


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
