"""Fail-closed imaging change. No volume store, no diagnosis, no alert_level."""
from __future__ import annotations

from fastapi import HTTPException, status

from app.services.consent import require_imaging_grant

MIN_COMPARABLE_VOLUMES = 2


def write_imaging_change(
    db,
    user_id,
    *,
    comparable_count: int = 0,
    same_sequence_family: bool = False,
) -> None:
    """Refuse a volume write. This is the only imaging writer.

    Order is binding: distinct consent purpose, then two comparable
    acquisitions of the same person. An incidental finding is not a boolean
    a client can set. A radiologist or the responsible psychiatrist signs it
    outside the app. Until that circuit exists, this function always refuses
    after the structural checks. It does not insert a DICOM/NIfTI row, does
    not emit a DSM label, and does not read or write alert_level.
    """
    require_imaging_grant(db, user_id)
    if comparable_count < MIN_COMPARABLE_VOLUMES or not same_sequence_family:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Imaging change requires two comparable volumes from the same person "
                "and sequence family. One scan is not a change."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Imaging ingest is blocked until a radiologist or the responsible psychiatrist "
            "signs incidental findings outside the app. That sign-off is not a client flag. "
            "Nothing is written to ChangeSignal or alert_level."
        ),
    )
