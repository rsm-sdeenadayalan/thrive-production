from django.urls import path

from .views import health

app_name = "rsm_thrive"

urlpatterns = [
    path("health", health.health, name="health"),
]
