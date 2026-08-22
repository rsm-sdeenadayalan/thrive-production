from django.db import models

EVENT_TYPE_CHOICES = [
    ("rady", "rady"), ("ucsd", "ucsd"), ("sandiego", "sandiego"),
    ("club", "club"), ("career", "career"),
]


class Event(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=16, choices=EVENT_TYPE_CHOICES, default="rady")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, default="")
    description = models.TextField(blank=True, default="")
    register_url = models.URLField(blank=True, default="")
    goal_tags = models.JSONField(default=list)  # lowercase role names this event serves
