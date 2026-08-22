from django.conf import settings
from django.db import models

TRACK_CHOICES = [("11 month", "11 month"), ("17 month", "17 month")]
STANDING_CHOICES = [("onTrack", "onTrack"), ("watch", "watch"), ("needsHelp", "needsHelp")]


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thrive_profile"
    )
    display_name = models.CharField(max_length=120)
    goal = models.CharField(max_length=120, blank=True, default="")
    track = models.CharField(max_length=16, choices=TRACK_CHOICES, default="11 month")
    program = models.CharField(max_length=120, default="MSBA")
    standing = models.CharField(max_length=16, choices=STANDING_CHOICES, default="onTrack")
    standing_summary = models.CharField(max_length=240, default="You're on track.")
    avatar_url = models.URLField(blank=True, default="")
    current_term = models.CharField(max_length=40, default="Fall 2026")
    program_start = models.DateField()
    consent_calendar_read = models.BooleanField(default=False)
    consent_lms_read = models.BooleanField(default=False)
    consent_career_recommendations = models.BooleanField(default=False)
    consent_advisor_sharing = models.BooleanField(default=False)
    tss_connected = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
