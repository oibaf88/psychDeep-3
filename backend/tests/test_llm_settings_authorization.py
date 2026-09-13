"""Authorization/route regressions for the privileged runtime model switch."""
import inspect

import pytest
from fastapi import HTTPException
from fastapi.params import Depends

from app.main import app
from app.models import User
from app.routers import llm_settings
from app.security import get_current_user, require_admin


def _user(role: str) -> User:
    return User(
        email=f"{role}@example.test",
        hashed_password="unused",
        display_name=role,
        role=role,
        locale="es-ES",
        is_active=True,
    )


def test_llm_settings_router_is_mounted():
    methods_by_path: dict[str, set[str]] = {}
    for route in app.routes:
        methods_by_path.setdefault(route.path, set()).update(getattr(route, "methods", set()) or set())

    assert "/api/v1/settings/llm" in methods_by_path
    assert {"GET", "PUT", "DELETE"}.issubset(methods_by_path["/api/v1/settings/llm"])
    assert "/api/v1/settings/llm/test" in methods_by_path
    assert "POST" in methods_by_path["/api/v1/settings/llm/test"]


def test_read_requires_authenticated_user():
    dependency = inspect.signature(llm_settings.read_llm_settings).parameters["user"].default
    assert isinstance(dependency, Depends)
    assert dependency.dependency is get_current_user


@pytest.mark.parametrize(
    "endpoint",
    [
        llm_settings.update_llm_settings,
        llm_settings.reset_llm_settings,
        llm_settings.test_llm_endpoint,
    ],
)
def test_every_mutation_requires_admin_clinical(endpoint):
    dependency = inspect.signature(endpoint).parameters["user"].default
    assert isinstance(dependency, Depends)
    assert dependency.dependency is require_admin


@pytest.mark.parametrize("role", ["patient", "therapist", "supervisor"])
def test_non_admin_roles_fail_admin_dependency(role):
    with pytest.raises(HTTPException) as exc:
        require_admin(_user(role))
    assert exc.value.status_code == 403


def test_admin_clinical_passes_admin_dependency():
    admin = _user("admin_clinical")
    assert require_admin(admin) is admin
