"""Small helpers shared across routers, schemas and services."""
from datetime import datetime, timezone


def as_utc(value: datetime | None) -> datetime | None:
    """Return ``value`` as an aware UTC datetime; naive DB timestamps are UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_iso(value: datetime | None) -> str | None:
    """Serialize legacy naive database timestamps explicitly as UTC ISO-8601."""
    aware = as_utc(value)
    return aware.isoformat() if aware is not None else None
