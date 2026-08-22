import datetime as dt

from django.utils import timezone


def iso_instant(value: dt.datetime) -> str:
    """ISO-8601 with offset, in the site timezone. The contract's ISODateTime."""
    if timezone.is_naive(value):
        raise ValueError("naive datetime crossed the serializer")
    return timezone.localtime(value).isoformat()


def iso_date(value: dt.date) -> str:
    """The contract's ISODate."""
    return value.isoformat()
