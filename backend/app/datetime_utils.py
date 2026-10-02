from datetime import datetime, timezone


def utc_iso(value: datetime | None) -> str | None:
    """Serialize legacy naive timestamps explicitly as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
