from django.urls import path

from .views import assignments, courses, events, health, resources, students, tasks

app_name = "rsm_thrive"

urlpatterns = [
    path("assignments", assignments.assignments, name="assignments"),
    path("courses", courses.courses, name="courses"),
    path("events", events.events, name="events"),
    path("health", health.health, name="health"),
    path("me", students.me, name="me"),
    path("resources", resources.resources, name="resources"),
    path("syllabi", courses.syllabi, name="syllabi"),
    path("tasks", tasks.tasks_dispatch, name="tasks"),
    path("tasks/<str:task_id>", tasks.delete_task, name="task-delete"),
    path("tasks/<str:task_id>/override", tasks.override, name="task-override"),
]
