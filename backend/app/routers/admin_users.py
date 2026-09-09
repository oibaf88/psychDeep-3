"""Administrative provisioning and role management for application users.

Public signup deliberately remains patient-only.  Privileged roles are created
or assigned through these endpoints, which are accessible only to an existing
``admin_clinical`` account.
"""
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Consent, SafetyPlan, User
from app.schemas import AccountDisplayName, AccountEmail
from app.security import hash_password, require_admin, validate_new_password
from app.services import audit

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])

UserRoleValue = Literal["patient", "therapist", "supervisor", "admin_clinical"]
ProfessionalRoleValue = Literal["therapist", "supervisor", "admin_clinical"]


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    role: UserRoleValue
    locale: str
    is_active: bool
    created_at: datetime


class AdminUserCreate(BaseModel):
    email: AccountEmail
    password: str = Field(min_length=12)
    display_name: AccountDisplayName
    role: ProfessionalRoleValue = "therapist"


class AdminRoleUpdate(BaseModel):
    role: UserRoleValue


class AdminUserPermissionsOut(BaseModel):
    """The deliberately small document shown/printed for one selected user."""

    user: AdminUserOut
    permissions: list[str]
    can_revoke: bool
    can_restore: bool


# These are application capabilities, not JWT claims. They stay server-side,
# derive from the database role on every request, and make the administrator's
# permission document understandable without revealing any clinical record.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "patient": [
        "Consultar y editar únicamente su propio seguimiento, diario, chat y plan de seguridad.",
        "Gestionar sus consentimientos, hechos declarados y notificaciones personales.",
        "No puede consultar expedientes, alertas ni datos de otras personas.",
    ],
    "therapist": [
        "Consultar la información clínica de pacientes que tenga asignados.",
        "Gestionar sus asignaciones, alertas y usar el copiloto profesional.",
        "No puede administrar usuarios, roles ni consultar la auditoría global.",
    ],
    "supervisor": [
        "Consultar la información clínica de pacientes que tenga asignados.",
        "Gestionar sus asignaciones, alertas y usar el copiloto profesional.",
        "Consultar la auditoría profesional; no puede administrar cuentas ni roles.",
    ],
    "admin_clinical": [
        "Gestionar cuentas profesionales, roles, activación y revocación de acceso.",
        "Consultar la auditoría y las asignaciones clínicas.",
        "Configurar el endpoint del LLM sólo cuando el despliegue lo permite; los cambios quedan auditados.",
        "No adquiere acceso clínico universal: los expedientes individuales siguen sujetos a las rutas y asignaciones del rol.",
    ],
}


def _active_admin_count(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.role == "admin_clinical", User.is_active == True)  # noqa: E712
        .count()
    )


def _permission_document(db: Session, target: User, acting_admin: User) -> AdminUserPermissionsOut:
    can_change_other = target.id != acting_admin.id
    is_last_active_admin = (
        target.role == "admin_clinical" and target.is_active and _active_admin_count(db) <= 1
    )
    return AdminUserPermissionsOut(
        user=AdminUserOut.model_validate(target),
        permissions=ROLE_PERMISSIONS[target.role],
        can_revoke=can_change_other and target.is_active and not is_last_active_admin,
        can_restore=can_change_other and not target.is_active,
    )


@router.get("", response_model=list[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List application users for the clinical-administration screen."""
    del admin  # authorization is performed by the dependency above
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def provision_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Create a non-patient account through the internal provisioning path."""
    existing = db.query(User).filter(func.lower(User.email) == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        validate_new_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Keep the same baseline processing-consent record used by public/demo
    # provisioning.  Professional accounts do not receive patient-only state.
    db.add(Consent(user_id=user.id, consent_type="data_processing", granted=True))
    db.commit()

    audit.log(
        db,
        actor_id=admin.id,
        actor_role=admin.role,
        action="professional_user_provisioned",
        entity_type="user",
        entity_id=user.id,
        extra={"role": user.role},
    )
    return AdminUserOut.model_validate(user)


@router.put("/{user_id}/role", response_model=AdminUserOut)
def change_user_role(
    user_id: uuid.UUID,
    payload: AdminRoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Promote or demote an existing user while preserving their stored data."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == admin.id and target.role != payload.role:
        # Prevent an administrator from accidentally locking themselves out of
        # the only UI that can repair role assignments.
        raise HTTPException(status_code=400, detail="You cannot change your own administrative role")

    if (
        target.role == "admin_clinical"
        and target.is_active
        and payload.role != "admin_clinical"
        and _active_admin_count(db) <= 1
    ):
        raise HTTPException(status_code=400, detail="Debe permanecer al menos un administrador clínico activo.")

    previous_role = target.role
    if previous_role == payload.role:
        return AdminUserOut.model_validate(target)

    target.role = payload.role
    target.auth_version = (target.auth_version or 1) + 1

    # A user moved back to the patient experience must have the patient-only
    # state expected by SafetyPlanPage.  Promotion never deletes patient data.
    if payload.role == "patient":
        safety_plan = db.query(SafetyPlan).filter(SafetyPlan.user_id == target.id).first()
        if not safety_plan:
            db.add(SafetyPlan(user_id=target.id))

    db.commit()
    db.refresh(target)

    audit.log(
        db,
        actor_id=admin.id,
        actor_role=admin.role,
        action="user_role_changed",
        entity_type="user",
        entity_id=target.id,
        extra={"previous_role": previous_role, "new_role": target.role},
    )
    return AdminUserOut.model_validate(target)


@router.get("/{user_id}/permissions", response_model=AdminUserPermissionsOut)
def get_user_permissions(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Return only the selected user's account/permission document."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    audit.log(
        db,
        actor_id=admin.id,
        actor_role=admin.role,
        action="user_permissions_viewed",
        entity_type="user",
        entity_id=target.id,
    )
    return _permission_document(db, target, admin)


@router.post("/{user_id}/permissions/print", response_model=AdminUserPermissionsOut)
def print_user_permissions(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Audit a browser-side Print-to-PDF request; never persist a sensitive PDF."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    audit.log(
        db,
        actor_id=admin.id,
        actor_role=admin.role,
        action="user_permissions_print_requested",
        entity_type="user",
        entity_id=target.id,
    )
    return _permission_document(db, target, admin)


@router.post("/{user_id}/revoke", response_model=AdminUserPermissionsOut)
def revoke_user_access(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes revocar tu propio acceso administrativo.")
    if not target.is_active:
        raise HTTPException(status_code=400, detail="La cuenta ya está revocada.")
    if target.role == "admin_clinical" and _active_admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Debe permanecer al menos un administrador clínico activo.")

    target.is_active = False
    target.auth_version = (target.auth_version or 1) + 1
    db.commit()
    db.refresh(target)
    audit.log(
        db,
        actor_id=admin.id,
        actor_role=admin.role,
        action="user_access_revoked",
        entity_type="user",
        entity_id=target.id,
        extra={"role": target.role},
    )
    return _permission_document(db, target, admin)


@router.post("/{user_id}/restore", response_model=AdminUserPermissionsOut)
def restore_user_access(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Tu cuenta administrativa no se restaura desde esta pantalla.")
    if target.is_active:
        raise HTTPException(status_code=400, detail="La cuenta ya está activa.")

    target.is_active = True
    # Old JWTs remain invalid after a restore; the account holder must sign in.
    target.auth_version = (target.auth_version or 1) + 1
    db.commit()
    db.refresh(target)
    audit.log(
        db,
        actor_id=admin.id,
        actor_role=admin.role,
        action="user_access_restored",
        entity_type="user",
        entity_id=target.id,
        extra={"role": target.role},
    )
    return _permission_document(db, target, admin)
