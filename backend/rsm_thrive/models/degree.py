from django.conf import settings
from django.db import models

from .students import STANDING_CHOICES, TRACK_CHOICES

PHASE_ID_CHOICES = [
    ("orientation", "orientation"), ("fall", "fall"), ("winter", "winter"),
    ("spring", "spring"), ("summer", "summer"), ("optional-fall", "optional-fall"),
]


class ProgramPhaseRow(models.Model):
    track = models.CharField(max_length=16, choices=TRACK_CHOICES)
    phase_id = models.CharField(max_length=16, choices=PHASE_ID_CHOICES)
    label = models.CharField(max_length=60)
    term = models.CharField(max_length=40)
    start = models.DateField()
    end = models.DateField()
    optional = models.BooleanField(default=False)

    class Meta:
        ordering = ["start"]
        constraints = [models.UniqueConstraint(fields=["track", "phase_id"],
                                               name="uniq_phase_per_track")]


class DegreeRequirement(models.Model):
    track = models.CharField(max_length=16, choices=TRACK_CHOICES, unique=True)
    units_required = models.PositiveSmallIntegerField()
    core_required = models.PositiveSmallIntegerField()
    elective_required = models.PositiveSmallIntegerField()


class DegreeGap(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(max_length=120)
    detail = models.CharField(max_length=400, default="")
    severity = models.CharField(max_length=16, choices=STANDING_CHOICES, default="watch")
