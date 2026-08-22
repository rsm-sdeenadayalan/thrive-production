from django.conf import settings
from django.db import models

TASK_SOURCE_CHOICES = [
    ("class", "class"), ("career", "career"), ("admin", "admin"), ("event", "event"),
]
PRIORITY_CHOICES = [("low", "low"), ("medium", "medium"), ("high", "high")]


class SharedTask(models.Model):
    title = models.CharField(max_length=200)
    due_date = models.DateTimeField()
    source = models.CharField(max_length=16, choices=TASK_SOURCE_CHOICES, default="admin")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="medium")
    subtasks = models.JSONField(default=list)  # [{"id","title","done"}]
    course = models.ForeignKey("rsm_thrive.Course", null=True, blank=True,
                               on_delete=models.SET_NULL)
    active = models.BooleanField(default=True)


class StudentTask(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    due_date = models.DateTimeField()
    source = models.CharField(max_length=16, choices=TASK_SOURCE_CHOICES, default="admin")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="medium")
    subtasks = models.JSONField(default=list)


class TaskOverride(models.Model):
    """Sparse per-student task edits. A null column = 'use the source value'."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task_key = models.CharField(max_length=80)
    done = models.BooleanField(null=True, blank=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES,
                                null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField(null=True, blank=True)
    subtask_done = models.JSONField(null=True, blank=True)  # {"subtaskId": bool}

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "task_key"], name="uniq_task_override"),
        ]
