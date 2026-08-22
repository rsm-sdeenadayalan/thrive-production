from django.db import models

RESOURCE_CATEGORY_CHOICES = [
    ("academic", "academic"), ("career", "career"), ("wellness", "wellness"),
    ("technical", "technical"), ("administrative", "administrative"),
]


class ResourceLink(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=400)
    url = models.URLField()
    category = models.CharField(max_length=20, choices=RESOURCE_CATEGORY_CHOICES)
    owner = models.CharField(max_length=120, blank=True, default="")
