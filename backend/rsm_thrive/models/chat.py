from django.conf import settings
from django.db import models
from django.utils import timezone

DESTINATION_CHOICES = [
    ("resources", "resources"), ("courses", "courses"), ("career", "career"),
]
ROLE_CHOICES = [("student", "student"), ("thrive", "thrive")]


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
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sent_at", "pk"]


class ChatTurnLog(models.Model):
    """Provenance for one assistant turn: which bot, which chunks, how long.

    The spec's diagnosability requirement: a wrong answer is traceable to the
    exact retrieved chunks in one look.
    """
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE,
                                   related_name="turn_log")
    bot = models.CharField(max_length=16)
    model_note = models.CharField(max_length=32)
    chunk_ids = models.JSONField(default=list)
    duration_ms = models.IntegerField(default=0)
