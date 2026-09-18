"""Gate local LM Studio use behind a PsychDeep session and manager approval.

The LM Studio API key still authenticates the origin. This module is the
application authorization layer: an anonymous caller, a revoked account, or
an account the clinical administrator has not approved must never obtain a
local-model provider.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import User


class LocalLlmAccessDenied(RuntimeError):
    """Raised when the signed-in account is not allowed to use LM Studio."""


def is_usable(user: object | None) -> bool:
    if user is None or not getattr(user, "is_active", False):
        return False
    if getattr(user, "role", None) == "admin_clinical":
        return True
    return bool(getattr(user, "local_llm_approved", False))


def public_status(user: User) -> dict:
    usable = is_usable(user)
    if getattr(user, "role", None) == "admin_clinical":
        reason = "manager"
    elif getattr(user, "local_llm_approved", False):
        reason = "approved"
    else:
        reason = "pending"
    return {
        "local_llm_approved": bool(getattr(user, "local_llm_approved", False)),
        "local_llm_usable": usable,
        "local_llm_access": reason,
    }


def assert_can_use_local_llm(user: object | None) -> None:
    if user is None:
        raise LocalLlmAccessDenied(
            "Se requiere una sesión activa en PsychDeep para usar el modelo local."
        )
    if not getattr(user, "is_active", False):
        raise LocalLlmAccessDenied("La cuenta no está activa.")
    if is_usable(user):
        return
    raise LocalLlmAccessDenied(
        "El administrador clínico debe autorizar tu cuenta antes de usar el modelo local."
    )


def request_user(db: Session | None) -> User | None:
    if db is None:
        return None
    info = getattr(db, "info", None)
    user_id = info.get("authenticated_user_id") if isinstance(info, dict) else None
    if user_id is None:
        return None
    return db.get(User, user_id)


def set_approval(db: Session, *, target: User, acting_admin: User, approved: bool) -> User:
    if approved:
        target.local_llm_approved = True
        target.local_llm_approved_at = datetime.now(timezone.utc)
        target.local_llm_approved_by = acting_admin.id
    else:
        target.local_llm_approved = False
        target.local_llm_approved_at = None
        target.local_llm_approved_by = None
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def clear_approval(target: User) -> None:
    target.local_llm_approved = False
    target.local_llm_approved_at = None
    target.local_llm_approved_by = None
