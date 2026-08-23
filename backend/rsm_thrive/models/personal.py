from django.conf import settings
from django.db import models


class CalendarItemLabel(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item_key = models.CharField(max_length=120)
    label = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "item_key"], name="uniq_item_label"),
        ]


class CalendarItemUrgent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    item_key = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "item_key"], name="uniq_item_urgent"),
        ]


class CustomCalendarEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=120)
    title = models.CharField(max_length=200)
    day_key = models.CharField(max_length=10)
    time = models.CharField(max_length=5, blank=True, default="")
    label = models.TextField(blank=True, default="")
    urgent = models.BooleanField(default=False)
    created_at_ms = models.BigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "key"], name="uniq_custom_event"),
        ]


class QuickListItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    created_at_ms = models.BigIntegerField()
    copied_from = models.CharField(max_length=120, blank=True, default="")
    due_date = models.CharField(max_length=64, blank=True, default="")
    note = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "key"], name="uniq_quick_item"),
        ]
