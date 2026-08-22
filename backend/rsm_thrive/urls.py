from django.urls import path

from .views import assignments, courses, degree, events, health, overlay, resources, students, tasks

app_name = "rsm_thrive"

urlpatterns = [
    path("assignments", assignments.assignments, name="assignments"),
    path("calendar-prefs", overlay.calendar_prefs, name="calendar-prefs"),
    path("courses", courses.courses, name="courses"),
    path("degree/progress", degree.progress, name="degree-progress"),
    path("degree/timeline", degree.timeline, name="degree-timeline"),
    path("events", events.events, name="events"),
    path("events/<str:event_id>/ignore", overlay.ignore_event, name="event-ignore"),
    path("events/<str:event_id>/join", overlay.join_event, name="event-join"),
    path("health", health.health, name="health"),
    path("me", students.me, name="me"),
    path("overlay", overlay.overlay, name="overlay"),
    path("resources", resources.resources, name="resources"),
    path("syllabi", courses.syllabi, name="syllabi"),
    path("tasks", tasks.tasks_dispatch, name="tasks"),
    path("tasks/<str:task_id>", tasks.delete_task, name="task-delete"),
    path("tasks/<str:task_id>/note", overlay.task_note, name="task-note"),
    path("tasks/<str:task_id>/override", tasks.override, name="task-override"),
]
