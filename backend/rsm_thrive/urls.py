from django.urls import path

from .views import assignments, health, students

app_name = "rsm_thrive"

urlpatterns = [
    path("health", health.health, name="health"),
    path("me", students.me, name="me"),
    path("assignments", assignments.assignments, name="assignments"),
]
