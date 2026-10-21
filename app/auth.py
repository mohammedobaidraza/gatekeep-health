import secrets
from fastapi import Depends, Header, HTTPException
from app.config import settings

# Permission sets per role
ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "system_admin": {
        "can_create": True,
        "can_terminate": True,
        "can_revoke_access": True,
        "can_view_all": True,
        "can_audit": True,
        "can_manage_roles": True,
    },
    "department_head": {
        "can_create": True,
        "can_terminate": False,
        "can_revoke_access": False,
        "can_view_all": True,
        "can_audit": True,
        "can_manage_roles": False,
    },
    "staff_coordinator": {
        "can_create": True,
        "can_terminate": False,
        "can_revoke_access": False,
        "can_view_all": True,
        "can_audit": False,
        "can_manage_roles": False,
    },
    "compliance_officer": {
        "can_create": False,
        "can_terminate": False,
        "can_revoke_access": True,
        "can_view_all": True,
        "can_audit": True,
        "can_manage_roles": False,
    },
}

_USERS_BY_EMAIL: dict[str, dict] = {
    settings.demo_admin_email: {
        "email": settings.demo_admin_email,
        "password": settings.demo_admin_password,
        "token": settings.demo_admin_token,
        "name": "System Administrator",
        "role": "system_admin",
    },
    settings.demo_head_email: {
        "email": settings.demo_head_email,
        "password": settings.demo_head_password,
        "token": settings.demo_head_token,
        "name": "Department Head",
        "role": "department_head",
    },
    settings.demo_coordinator_email: {
        "email": settings.demo_coordinator_email,
        "password": settings.demo_coordinator_password,
        "token": settings.demo_coordinator_token,
        "name": "Staff Coordinator",
        "role": "staff_coordinator",
    },
    settings.demo_compliance_email: {
        "email": settings.demo_compliance_email,
        "password": settings.demo_compliance_password,
        "token": settings.demo_compliance_token,
        "name": "Compliance Officer",
        "role": "compliance_officer",
    },
}

_USERS_BY_TOKEN: dict[str, dict] = {
    u["token"]: u for u in _USERS_BY_EMAIL.values()
}


def authenticate(email: str, password: str) -> dict | None:
    user = _USERS_BY_EMAIL.get(email.lower())
    if not user:
        return None
    if not secrets.compare_digest(password, user["password"]):
        return None
    return user


def require_auth(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    user = _USERS_BY_TOKEN.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")
    role = user["role"]
    return {
        "email": user["email"],
        "name": user["name"],
        "role": role,
        "permissions": ROLE_PERMISSIONS[role],
    }


def require_permission(permission: str):
    """Return a FastAPI dependency that gates on a specific role permission."""
    def _check(user: dict = Depends(require_auth)) -> dict:
        if not user["permissions"].get(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Your role ('{user['role']}') does not have permission: {permission}",
            )
        return user
    return _check


# Back-compat alias — existing endpoints that used require_admin still work
require_admin = require_auth
