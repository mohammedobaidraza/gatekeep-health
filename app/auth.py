from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import decode_access_token, verify_password

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


def authenticate(db: Session, email: str, password: str):
    """Verify credentials against the DB. Returns the User ORM object or None."""
    from app.models import User
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return user


def _user_to_dict(user) -> dict:
    role = user.role
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": role,
        "must_change_password": user.must_change_password,
        "permissions": ROLE_PERMISSIONS.get(role, {}),
    }


def require_auth(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")
    token = authorization.removeprefix("Bearer ")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    from app.models import User
    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account not found or deactivated")
    return _user_to_dict(user)


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


# Back-compat alias
require_admin = require_auth
