"""Console admin for third-party integration records.

AdvisorCalendarConnection stores MS Graph OAuth tokens. The console
auto-registers every model, which would expose those tokens to staff; this
explicit admin hides them (they are never shown or hand-editable) and leaves
only safe metadata visible.
"""

from django.contrib import admin

from rsm_thrive.models import AdvisorCalendarConnection

from .base import ConsoleModelAdmin


@admin.register(AdvisorCalendarConnection)
class AdvisorCalendarConnectionAdmin(ConsoleModelAdmin):
    list_display = ("advisor", "account_email", "expires_at", "updated_at")
    search_fields = ("advisor__name", "account_email")
    # Never expose the OAuth tokens in the form or detail view.
    exclude = ("access_token", "refresh_token")
    readonly_fields = ("advisor", "account_email", "expires_at",
                       "created_at", "updated_at")

    def has_add_permission(self, request):
        # Connections are created through the OAuth flow, not by hand.
        return False
