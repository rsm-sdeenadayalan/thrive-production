"""Operations — run the system's management commands from the console.

The content tool covers corpus ingest; this covers the rest of the operational
surface (rebuild catalog, refresh jobs, retry notifications, reports, evals,
seed). Admin-only. Commands run synchronously and their output tail is shown.
Only whitelisted commands are runnable — the console never shells arbitrary
management commands.
"""

import io

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import models
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path

from .access import is_thrive_admin

HUB_URL = "admin:rsm_thrive_operation_changelist"

# name -> (label, help). Only these may be run from the console.
OPERATIONS = {
    "build_catalog": ("Rebuild catalog",
                      "Regenerate courses.json from the syllabi markdown."),
    "ingest_jobs": ("Refresh job postings",
                    "Fetch and upsert postings from configured sources."),
    "retry_notifications": ("Retry failed notifications",
                            "Re-send appointment Zoom/email notifications that failed."),
    "refusal_report": ("Refusal report",
                       "List questions the bots refused — the content backlog."),
    "export_golden": ("Export eval cases",
                      "Turn thumbs-down feedback into golden eval cases."),
    "eval_bots": ("Run bot evals",
                  "Run golden cases through the bots (resources/career under FakeLLM)."),
    "seed_demo": ("Seed demo data",
                  "Populate an idempotent demo world for testing."),
}


class Operation(models.Model):
    """Not a table — hosts the operations admin page."""

    class Meta:
        managed = False
        app_label = "rsm_thrive"
        verbose_name = "operation"
        verbose_name_plural = "Operations"

    def __str__(self):
        return "Operations"


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return is_thrive_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_thrive_admin(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        base = super().get_urls()
        custom = [
            path("run/", self.admin_site.admin_view(self.run_view),
                 name="operation_run"),
        ]
        return custom + base

    def changelist_view(self, request, extra_context=None):
        if not is_thrive_admin(request.user):
            raise PermissionDenied
        ctx = {
            **self.admin_site.each_context(request),
            "title": "Operations",
            "operations": [(name, label, help_) for name, (label, help_)
                           in OPERATIONS.items()],
        }
        return TemplateResponse(request, "admin/operations/hub.html", ctx)

    def run_view(self, request):
        if not is_thrive_admin(request.user):
            raise PermissionDenied
        if request.method != "POST":
            return redirect(HUB_URL)

        command = request.POST.get("command", "")
        if command not in OPERATIONS:
            messages.error(request, "Unknown or disallowed command.")
            return redirect(HUB_URL)

        out = io.StringIO()
        try:
            call_command(command, stdout=out, stderr=out)
        except Exception as err:
            messages.error(request, f"{command} failed: {err}")
        else:
            tail = out.getvalue().strip().splitlines()[-4:]
            messages.success(request, f"{command} done. " + " · ".join(tail))
        return redirect(HUB_URL)
