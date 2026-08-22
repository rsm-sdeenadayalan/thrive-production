from django.urls import path

from .views import assignments, courses, events, health, students

app_name = "rsm_thrive"

urlpatterns = [
    path("assignments", assignments.assignments, name="assignments"),
    path("courses", courses.courses, name="courses"),
    path("events", events.events, name="events"),
    path("health", health.health, name="health"),
    path("me", students.me, name="me"),
    path("syllabi", courses.syllabi, name="syllabi"),
]
