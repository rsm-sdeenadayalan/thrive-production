"""Console admins: advisors, appointments, and events."""

from django.contrib import admin

from rsm_thrive.models import (Advisor, Appointment, AppointmentNotification,
                               AppointmentSlot, Event)

from .base import ConsoleModelAdmin


class AppointmentSlotInline(admin.TabularInline):
    model = AppointmentSlot
    extra = 0


@admin.register(Advisor)
class AdvisorAdmin(ConsoleModelAdmin):
    list_display = ("name", "role", "service", "email", "location")
    list_filter = ("service",)
    search_fields = ("name", "email", "role")
    inlines = [AppointmentSlotInline]


@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(ConsoleModelAdmin):
    list_display = ("advisor", "start", "end", "mode")
    list_filter = ("mode", "advisor")
    date_hierarchy = "start"


class AppointmentNotificationInline(admin.TabularInline):
    model = AppointmentNotification
    extra = 0


@admin.register(Appointment)
class AppointmentAdmin(ConsoleModelAdmin):
    list_display = ("student", "slot", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("student__username", "reason")
    date_hierarchy = "created_at"
    inlines = [AppointmentNotificationInline]


@admin.register(AppointmentNotification)
class AppointmentNotificationAdmin(ConsoleModelAdmin):
    list_display = ("appointment", "kind", "status", "attempts")
    list_filter = ("kind", "status")


@admin.register(Event)
class EventAdmin(ConsoleModelAdmin):
    list_display = ("title", "type", "start", "location")
    list_filter = ("type",)
    search_fields = ("title", "location")
    date_hierarchy = "start"
