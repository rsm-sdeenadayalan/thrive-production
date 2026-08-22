from django.core.management.base import BaseCommand

from rsm_thrive.models import AppointmentNotification
from rsm_thrive.services import notifications as svc


class Command(BaseCommand):
    help = "Retry failed appointment notifications (zoom / invite emails)."

    def handle(self, *args, **options):
        failed = list(AppointmentNotification.objects.filter(status="failed"))
        sent = 0
        for row in failed:
            appointment = row.appointment
            if row.kind != "email_cancel" and appointment.status != "confirmed":
                continue
            before = set(appointment.notifications.values_list("pk", flat=True))
            if row.kind == "zoom":
                svc._create_zoom(appointment)
            elif row.kind == "email_request":
                svc._send_invite(appointment, "REQUEST", "email_request")
            else:
                svc._send_invite(appointment, "CANCEL", "email_cancel")
            new = appointment.notifications.exclude(pk__in=before).first()
            if new is not None:
                row.status, row.detail = new.status, new.detail
                row.attempts += 1
                row.save(update_fields=["status", "detail", "attempts", "updated_at"])
                new.delete()
                if row.status == "sent":
                    sent += 1
        self.stdout.write(f"retried {len(failed)}: {sent} sent, "
                          f"{len(failed) - sent} still failed/skipped")
