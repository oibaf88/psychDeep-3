import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

_BCRYPT_MAX_BYTES = 72
_PASSWORD_MIN_LENGTH = 12


def validate_new_password(password: str) -> None:
    """Avoid bcrypt's silent 72-byte truncation on newly issued passwords."""
    if not isinstance(password, str) or len(password) < _PASSWORD_MIN_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {_PASSWORD_MIN_LENGTH} caracteres.")
    if len(password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise ValueError("La contraseña supera el límite seguro de 72 bytes de bcrypt.")


def hash_password(password: str) -> str:
    validate_new_password(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:_BCRYPT_MAX_BYTES], hashed.encode("utf-8"))
    except (ValueError, TypeError, AttributeError):
        return False


def create_access_token(user_id: uuid.UUID, role: str, auth_version: int = 1) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "av": auth_version, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        auth_version = payload.get("av")
        if user_id is None or not isinstance(auth_version, int):
            raise credentials_exception
        user_id = uuid.UUID(user_id)
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)
    current_auth_version = getattr(user, "auth_version", 1) if user is not None else 1
    if not isinstance(current_auth_version, int):
        current_auth_version = 1
    if user is None or not user.is_active or auth_version != current_auth_version:
        raise credentials_exception
    # Session.info belongs to THIS request's database session, not process-wide
    # state. Provider calls must not infer ownership from patient dossier data.
    if isinstance(getattr(db, "info", None), dict):
        db.info["authenticated_user_id"] = user.id
    return user


def require_roles(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _dep


require_patient = require_roles("patient")
require_professional = require_roles("therapist", "supervisor", "admin_clinical")
require_admin = require_roles("admin_clinical")
