from django.conf import settings
from django.db import models

from .students import STANDING_CHOICES

ASSIGNMENT_STATUS_CHOICES = [
    ("not-started", "not-started"),
    ("in-progress", "in-progress"),
    ("submitted", "submitted"),
    ("graded", "graded"),
    ("late", "late"),
]
BUCKET_CHOICES = [("core", "core"), ("elective", "elective")]


class Course(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    code = models.CharField(max_length=32)
    title = models.CharField(max_length=200)
    instructor = models.CharField(max_length=120)
    term = models.CharField(max_length=40)
    units = models.PositiveSmallIntegerField(default=4)


class CourseMeeting(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="meetings")
    day_of_week = models.PositiveSmallIntegerField()  # 0=Sunday..6, matches JS getDay()
    start_time = models.CharField(max_length=5)  # wall-clock "HH:mm", per contract
    end_time = models.CharField(max_length=5)
    location = models.CharField(max_length=120)

    class Meta:
        ordering = ["day_of_week", "start_time"]


class Syllabus(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="syllabus")
    description = models.TextField()
    grade_breakdown = models.JSONField(default=list)  # [{"label": str, "weight": int}]
    policies = models.JSONField(default=list)  # [str]
    office_hours = models.CharField(max_length=200, default="")
    source_url = models.URLField(blank=True, default="")
    last_updated = models.DateField()


class Assignment(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    due_date = models.DateTimeField()
    weight = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True, default="")


class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    progress = models.PositiveSmallIntegerField(default=0)  # 0-100
    standing = models.CharField(max_length=16, choices=STANDING_CHOICES, default="onTrack")
    current_grade = models.CharField(max_length=16, blank=True, default="")
    nudge = models.CharField(max_length=240, blank=True, default="")
    bucket = models.CharField(max_length=16, choices=BUCKET_CHOICES, default="core")
    completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment"),
        ]


class StudentAssignment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=ASSIGNMENT_STATUS_CHOICES, default="not-started")
    grade = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "assignment"], name="uniq_student_assignment"),
        ]
