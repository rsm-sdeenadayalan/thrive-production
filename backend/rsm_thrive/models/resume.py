from django.conf import settings
from django.db import models
from django.db.models import Q

SKILL_SOURCE_CHOICES = [("course", "course"), ("manual", "manual")]


class Skill(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    source = models.CharField(max_length=16, choices=SKILL_SOURCE_CHOICES,
                              default="manual")
    course = models.ForeignKey("rsm_thrive.Course", null=True, blank=True,
                               on_delete=models.SET_NULL)


class ResumeCourseHighlight(models.Model):
    code = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=200)
    highlight = models.CharField(max_length=240)


class ResumeVersion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    summary = models.TextField()
    skills = models.JSONField(default=list)      # frozen contract-shaped snapshots
    courses = models.JSONField(default=list)
    experience = models.JSONField(default=list)
    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user"], condition=Q(is_current=True),
                                    name="uniq_current_resume"),
        ]
