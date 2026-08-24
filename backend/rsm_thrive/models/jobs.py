from django.conf import settings
from django.db import models
from django.utils import timezone

COMPETENCY_CHOICES = [("strong", "strong"), ("good", "good"),
                      ("stretch", "stretch"), ("reach", "reach")]


class JobPosting(models.Model):
    """One normalized posting from any source. Shared across users."""
    source = models.CharField(max_length=32)          # greenhouse | lever | fake | adzuna(later)
    external_id = models.CharField(max_length=120)
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=120)
    location = models.CharField(max_length=160, blank=True)
    url = models.URLField()
    description = models.TextField()
    posted_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    skills = models.JSONField(default=list)
    embedding = models.JSONField(default=list)
    content_hash = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["source", "external_id"], name="uniq_job_source_external")]


class MatchReport(models.Model):
    """Stage-2 LLM verdict, cached per (user, posting, resume version)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE,
                                related_name="reports")
    resume_version = models.ForeignKey("rsm_thrive.ResumeVersion",
                                       on_delete=models.CASCADE)
    competency = models.CharField(max_length=16, choices=COMPETENCY_CHOICES)
    score = models.IntegerField()  # 0-100
    matched_skills = models.JSONField(default=list)
    gaps = models.JSONField(default=list)
    verdict = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "posting", "resume_version"], name="uniq_match_report")]


class PostingInteraction(models.Model):
    """Per-student like/dismiss state on a posting."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="posting_interactions")
    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE,
                                related_name="interactions")
    liked = models.BooleanField(default=False)
    dismissed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "posting"], name="uniq_posting_interaction")]
