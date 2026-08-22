from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/thrive/", include("rsm_thrive.urls")),
]
