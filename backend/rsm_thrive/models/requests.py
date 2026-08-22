from django.conf import settings
from django.db import models

REQUEST_TYPE_CHOICES = [
    ("enroll", "enroll"), ("drop", "drop"),
    ("reduced load", "reduced load"), ("out of major", "out of major"),
]
REQUEST_STATUS_CHOICES = [
    ("draft", "draft"), ("submitted", "submitted"),
    ("approved", "approved"), ("denied", "denied"),
]


class CourseRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=16, choices=REQUEST_TYPE_CHOICES)
    course = models.CharField(max_length=200)
    reason = models.TextField()
    status = models.CharField(max_length=16, choices=REQUEST_STATUS_CHOICES,
                              default="draft")
    submitted_at = models.DateTimeField(null=True, blank=True)
    prefill = models.JSONField(default=dict)  # snapshot at creation, never recomputed
    created_at = models.DateTimeField(auto_now_add=True)
