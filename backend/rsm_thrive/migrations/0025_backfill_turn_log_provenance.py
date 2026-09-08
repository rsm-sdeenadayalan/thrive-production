"""Give the turns already in the database the columns the trace view reads.

Without this every historic turn reads as "asked nothing, at the moment of the
deploy, never refused" — three claims that are false, in the one table whose
whole purpose is being trustworthy about what happened.

`created_at` comes from the reply's own `sent_at`; `question` from the student
turn immediately above it in the same conversation; `refused` from the only
signal the old rows carry, `model_note == "refusal"`.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    ChatTurnLog = apps.get_model("rsm_thrive", "ChatTurnLog")
    ChatMessage = apps.get_model("rsm_thrive", "ChatMessage")

    logs = list(ChatTurnLog.objects.select_related("message"))
    if not logs:
        return
    conversation_ids = {log.message.conversation_id for log in logs}
    by_conversation = {}
    for message in (ChatMessage.objects
                    .filter(conversation_id__in=conversation_ids)
                    .order_by("conversation_id", "sent_at", "pk")):
        by_conversation.setdefault(message.conversation_id, []).append(message)

    for log in logs:
        reply = log.message
        rows = by_conversation.get(reply.conversation_id, [])
        asked = ""
        for index, message in enumerate(rows):
            if message.pk != reply.pk:
                continue
            for earlier in reversed(rows[:index]):
                if earlier.role == "student":
                    asked = earlier.body
                    break
            break
        log.question = asked
        log.created_at = reply.sent_at
        log.refused = log.model_note == "refusal"
    ChatTurnLog.objects.bulk_update(logs, ["question", "created_at", "refused"])


class Migration(migrations.Migration):

    dependencies = [
        ("rsm_thrive", "0024_turnfeedback_alter_chatturnlog_options_and_more"),
    ]

    # Reverse is a no-op rather than an error: the columns themselves are
    # dropped by unapplying 0024, so there is nothing for this to undo.
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
