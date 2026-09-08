from django.conf import settings
from django.db import models
from django.utils import timezone

DESTINATION_CHOICES = [
    ("resources", "resources"), ("courses", "courses"), ("career", "career"),
]
ROLE_CHOICES = [("student", "student"), ("thrive", "thrive")]
RATING_CHOICES = [("up", "up"), ("down", "down")]


class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    destination = models.CharField(max_length=16, choices=DESTINATION_CHOICES)
    title = models.CharField(max_length=200)
    updated_at = models.DateTimeField(default=timezone.now)  # when the last message landed


class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
                                     related_name="messages")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    body = models.TextField()
    # [{"label": str, "send": str}] — choices offered with this reply, rendered
    # as buttons. Stored rather than recomputed so reopening a conversation
    # shows the same choices it showed at the time: the question a student was
    # asked is part of the record, not something to re-derive from a prompt that
    # may since have changed.
    quick_replies = models.JSONField(default=list, blank=True)
    # An interactive form offered with this reply, or null. Same reasoning as
    # `quick_replies`: what a student was asked is part of the record.
    form = models.JSONField(null=True, blank=True, default=None)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sent_at", "pk"]


class ChatTurnLog(models.Model):
    """Provenance for one assistant turn: which bot, which route, which chunks.

    The spec's diagnosability requirement: a wrong answer is traceable to the
    exact retrieved chunks in one look.

    "In one look" is why `question` is denormalised onto this row rather than
    read back off the sibling `ChatMessage`. Finding the student turn a reply
    answered means ordering the conversation's messages and stepping backwards
    one row, which is an assumption about ordering rather than a fact about the
    turn — and it makes the single most useful filter (all the turns that asked
    about prerequisites) a join plus a scan instead of a `LIKE`.
    """
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE,
                                   related_name="turn_log")
    bot = models.CharField(max_length=16)
    model_note = models.CharField(max_length=32)
    chunk_ids = models.JSONField(default=list)
    duration_ms = models.IntegerField(default=0)
    # What the student actually asked, copied from the student turn above.
    question = models.TextField(blank=True, default="")
    # Which route the orchestrator picked, and how sure it was. Blank on turns
    # answered before the orchestrator existed, and on the paths that never go
    # through it. `route_confidence` is null when the route came from a rule
    # rather than from a model — a rule is not 1.0-confident, it is not a
    # probability at all, and recording it as one would make the two
    # indistinguishable in the very report that exists to tell them apart.
    route = models.CharField(max_length=32, blank=True, default="")
    route_confidence = models.FloatField(null=True, blank=True)
    # Set when the turn declined to answer. Kept as its own column rather than
    # inferred from `model_note` at read time because the refusal report is a
    # CONTENT BACKLOG — the questions the corpus cannot answer, written by the
    # people who need them answered — and a backlog that depends on parsing a
    # free-text note is a backlog that silently loses rows when the note's
    # vocabulary changes.
    refused = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["refused", "-created_at"]),
            models.Index(fields=["route", "-created_at"]),
        ]

    def __str__(self):
        return f"turn {self.pk} ({self.bot}/{self.route or self.model_note})"


class TurnFeedback(models.Model):
    """A tester's verdict on one answer.

    Hung off `ChatTurnLog` rather than off `ChatMessage`, because a verdict is
    only worth anything next to the evidence: the route that was taken, the
    chunks that were retrieved and how long it took are what turn "that answer
    was bad" into a diagnosis. A rating with no trace beside it is a complaint.

    One row per turn, updated in place. A tester who clicks down, reads it
    again and clicks up has changed their mind, not filed a second report — and
    a table of contradictory rows for the same answer cannot be counted.
    """
    turn = models.OneToOneField(ChatTurnLog, on_delete=models.CASCADE,
                                related_name="feedback")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.CharField(max_length=8, choices=RATING_CHOICES)
    # Optional, and asked for only after the thumb is already recorded. The
    # click is the datum we are certain of; making it conditional on someone
    # typing a sentence is how twenty testers become three.
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        indexes = [models.Index(fields=["rating", "-updated_at"])]

    def __str__(self):
        return f"{self.rating} on turn {self.turn_id}"
