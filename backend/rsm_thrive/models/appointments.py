from django.conf import settings
from django.db import models
from django.db.models import Q

SERVICE_CHOICES = [("advising", "advising"), ("career", "career")]
MODE_CHOICES = [("in person", "in person"), ("zoom", "zoom")]
APPOINTMENT_STATUS_CHOICES = [("confirmed", "confirmed"), ("cancelled", "cancelled")]
NOTIFICATION_KIND_CHOICES = [
    ("zoom", "zoom"), ("email_request", "email_request"), ("email_cancel", "email_cancel"),
]
NOTIFICATION_STATUS_CHOICES = [("sent", "sent"), ("failed", "failed"), ("skipped", "skipped")]


class Advisor(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    service = models.CharField(max_length=16, choices=SERVICE_CHOICES)
    avatar_url = models.URLField(blank=True, default="")
    location = models.CharField(max_length=200)
    blurb = models.CharField(max_length=240, blank=True, default="")
    email = models.EmailField()  # internal: invite recipient, never serialized


class AppointmentSlot(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    advisor = models.ForeignKey(Advisor, on_delete=models.CASCADE, related_name="slots")
    start = models.DateTimeField()
    end = models.DateTimeField()
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default="zoom")


class Appointment(models.Model):
    slot = models.ForeignKey(AppointmentSlot, on_delete=models.PROTECT)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=16, choices=APPOINTMENT_STATUS_CHOICES,
                              default="confirmed")
    zoom_join_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["slot"], condition=Q(status="confirmed"),
                name="uniq_confirmed_slot",
            ),
        ]


class AppointmentNotification(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE,
                                    related_name="notifications")
    kind = models.CharField(max_length=16, choices=NOTIFICATION_KIND_CHOICES)
    status = models.CharField(max_length=16, choices=NOTIFICATION_STATUS_CHOICES)
    detail = models.TextField(blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
