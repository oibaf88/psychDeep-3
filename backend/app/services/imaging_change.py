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
    incidental_protocol: bool = False,
) -> None:
    """Refuse a volume write. This is the only imaging writer.

    Order is binding: consent purpose first, then two comparable acquisitions
    of the same person, then a human incidental-finding path. There is no
    DICOM/NIfTI table and this function does not insert one. It does not read
    or write RiskAssessment.alert_level and it does not emit a DSM label.
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
    if not incidental_protocol:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Imaging ingest is blocked until a human incidental-finding protocol "
                "exists. Incidental findings are not written to ChangeSignal or alert_level."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="No versioned volume store. Imaging change is not written.",
    )
