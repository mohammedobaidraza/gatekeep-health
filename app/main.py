import contextvars
import csv
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import StringIO

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent, step_emitter
from app.agent.schemas import AgentRunRequest, AgentRunResponse
from app.auth import authenticate, require_auth, require_permission
from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import AuditEvent, CompanyAsset, Employee, EmployeeAccount, TerminationRun, User
from app.schemas import (
    AccountCreate, AssetTransferRequest, ChangePasswordRequest,
    EmployeeCreate, EmployeePatch, LoginRequest, RevokeRequest,
    TerminationRequest, UserCreate, UserOut, UserPatch,
)
from app.security import create_access_token, hash_password
from app.services import (
    ACCESS_TEMPLATES, add_account, audit, auto_provision,
    employee_detail, employee_summary, reactivate_employee,
    reset_demo, restore_account, revoke_account,
    serialize_account, terminate, termination_preview, utcnow,
)

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Seed demo users on first boot if the users table is empty
    db = SessionLocal()
    try:
        if db.scalar(select(func.count()).select_from(User)) == 0:
            reset_demo(db)
    finally:
        db.close()
    yield


app = FastAPI(title="GateKeep Health API", version="4.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Meta ───────────────────────────────────────────────────────────────────────

@app.get("/")
def landing():
    return {
        "name": "GateKeep Health",
        "tagline": "Clinical access management — every credential controlled, every departure secured.",
        "login_url": "/api/v1/auth/login",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "gatekeep-health", "version": "4.0.0"}


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token(user.id, user.email, user.name, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user.email, "name": user.name, "role": user.role, "must_change_password": user.must_change_password},
    }


@app.get("/api/v1/auth/me")
def me(user=Depends(require_auth)):
    return user


@app.post("/api/v1/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    user=Depends(require_auth),
    db: Session = Depends(get_db),
):
    from app.security import verify_password
    db_user = db.get(User, user["id"])
    if not db_user:
        raise HTTPException(404, "User not found")
    if not verify_password(payload.current_password, db_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    db_user.hashed_password = hash_password(payload.new_password)
    db_user.must_change_password = False
    db.commit()
    return {"status": "password changed"}


# ── System User Management (admin only) ────────────────────────────────────────

@app.get("/api/v1/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user=Depends(require_permission("can_manage_roles"))):
    return db.scalars(select(User).order_by(User.name)).all()


@app.post("/api/v1/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db), user=Depends(require_permission("can_manage_roles"))):
    if db.scalar(select(User).where(User.email == str(payload.email).lower())):
        raise HTTPException(409, "Email already exists")
    new_user = User(
        email=str(payload.email).lower(),
        name=payload.name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        must_change_password=True,
        created_by=user["email"],
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    # Send welcome email (fire-and-forget, won't block if Resend not configured)
    try:
        from app.email import send_welcome
        send_welcome(new_user.email, new_user.name, new_user.role, payload.password)
    except Exception:
        pass
    return new_user


@app.patch("/api/v1/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserPatch, db: Session = Depends(get_db), user=Depends(require_permission("can_manage_roles"))):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(target, k, v)
    db.commit()
    db.refresh(target)
    return target


@app.post("/api/v1/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("can_manage_roles")),
):
    import secrets as _secrets
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == user["id"]:
        raise HTTPException(400, "Use /auth/change-password to change your own password")
    temp = _secrets.token_urlsafe(12)
    target.hashed_password = hash_password(temp)
    target.must_change_password = True
    db.commit()
    return {"status": "password reset", "temp_password": temp}


# ── Demo ───────────────────────────────────────────────────────────────────────

@app.post("/api/v1/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    reset_demo(db)
    return {"status": "reset", "staff": 7, "users": 4}


# ── Access Templates ───────────────────────────────────────────────────────────

@app.get("/api/v1/access-templates")
def list_access_templates(user=Depends(require_auth)):
    return [
        {"key": k, "name": t["name"], "department": t["department"],
         "description": t["description"], "accounts": t["accounts"]}
        for k, t in ACCESS_TEMPLATES.items()
    ]


# ── Staff (Employees) ──────────────────────────────────────────────────────────

@app.get("/api/v1/employees")
def list_employees(
    db: Session = Depends(get_db),
    user=Depends(require_auth),
    q: str | None = Query(default=None, description="Search by name, email, or job title"),
    department: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    query = select(Employee).order_by(Employee.full_name)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                Employee.full_name.ilike(pattern),
                Employee.company_email.ilike(pattern),
                Employee.job_title.ilike(pattern),
            )
        )
    if department:
        query = query.where(Employee.department.ilike(f"%{department}%"))
    if status:
        query = query.where(Employee.employment_status == status)
    return [employee_summary(e) for e in db.scalars(query).all()]


@app.post("/api/v1/employees")
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db), user=Depends(require_permission("can_create"))):
    if db.scalar(select(Employee).where(Employee.company_email == str(payload.company_email))):
        raise HTTPException(409, "Company email already exists")

    dept = payload.department.lower()
    base_risk = (
        75 if any(kw in dept for kw in ["medicine", "surgery", "icu", "emergency"]) else
        65 if any(kw in dept for kw in ["pharmacy", "nursing"]) else
        55 if any(kw in dept for kw in ["radiology", "imaging"]) else
        45 if "it" in dept or "security" in dept else 35
    )

    e = Employee(
        full_name=payload.full_name,
        company_email=str(payload.company_email),
        personal_email=str(payload.personal_email) if payload.personal_email else None,
        department=payload.department,
        job_title=payload.job_title,
        manager_name=payload.manager_name,
        start_date=payload.start_date,
        employment_status=payload.employment_status,
        risk_score=base_risk,
        npi_number=payload.npi_number,
        license_number=payload.license_number,
        license_state=payload.license_state,
        license_type=payload.license_type,
        dea_number=payload.dea_number,
        privilege_level=payload.privilege_level,
        credential_expiry=payload.credential_expiry,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    add_account(db, e, "Staff Directory", e.company_email, "Employee", "low", "directory", sessions=0)

    if payload.auto_provision:
        try:
            auto_provision(db, e, payload.access_template)
        except ValueError as error:
            raise HTTPException(400, str(error))

    audit(db, e.id, user["email"], "credential_clinician", e.company_email, "completed",
          "Clinical staff record and system access provisioned")
    return employee_detail(e)


@app.get("/api/v1/employees/{employee_id}")
def get_employee(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    return employee_detail(e)


@app.patch("/api/v1/employees/{employee_id}")
def patch_employee(employee_id: int, payload: EmployeePatch, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    e.updated_at = utcnow()
    db.commit()
    audit(db, e.id, user["email"], "update_clinician", e.company_email, "completed",
          json.dumps(payload.model_dump(exclude_unset=True), default=str))
    return employee_detail(e)


# ── Accounts ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/employees/{employee_id}/accounts")
def employee_accounts(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Clinician not found")
    return [serialize_account(a) for a in db.scalars(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == employee_id).order_by(EmployeeAccount.platform)
    ).all()]


@app.post("/api/v1/employees/{employee_id}/accounts")
def create_account(employee_id: int, payload: AccountCreate, db: Session = Depends(get_db), user=Depends(require_permission("can_create"))):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    a = add_account(db, e, payload.platform, payload.identifier, payload.access_level,
                    payload.risk_level, payload.account_type, payload.metadata,
                    payload.session_count, payload.credentials)
    db.commit()
    audit(db, e.id, user["email"], "add_account", payload.platform, "completed", payload.identifier)
    return serialize_account(a)


@app.post("/api/v1/accounts/{account_id}/revoke")
def account_revoke(account_id: int, payload: RevokeRequest, db: Session = Depends(get_db), user=Depends(require_permission("can_revoke_access"))):
    a = db.get(EmployeeAccount, account_id)
    if not a:
        raise HTTPException(404, "Account not found")
    return revoke_account(db, a, user["email"], payload.reason, payload.action)


@app.post("/api/v1/accounts/{account_id}/restore")
def account_restore(account_id: int, db: Session = Depends(get_db), user=Depends(require_permission("can_revoke_access"))):
    a = db.get(EmployeeAccount, account_id)
    if not a:
        raise HTTPException(404, "Account not found")
    if a.status == "active":
        raise HTTPException(400, "Account is already active")
    restored = restore_account(db, a, user["email"])
    return {**restored, "sessions_restored": False, "credentials_restored": False,
            "message": "Account restored. Previous sessions and credentials remain revoked."}


@app.post("/api/v1/accounts/{account_id}/verify")
def account_verify(account_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    a = db.get(EmployeeAccount, account_id)
    if not a:
        raise HTTPException(404, "Account not found")
    remaining_sessions = any(s.active for s in a.sessions)
    remaining_credentials = any(c.status == "active" for c in a.credentials)
    verified = (
        a.status in {"revoked", "frozen", "cancelled", "disabled"}
        and not remaining_sessions
        and not remaining_credentials
    )
    a.revocation_verified = verified
    db.commit()
    audit(db, a.employee_id, user["email"], "verify_account", a.platform,
          "verified" if verified else "failed", a.identifier)
    return {"account_id": a.id, "verified": verified, "status": a.status,
            "remaining_sessions": remaining_sessions, "remaining_credentials": remaining_credentials}


# ── Reactivate / Terminate ─────────────────────────────────────────────────────

@app.post("/api/v1/employees/{employee_id}/reactivate")
def reactivate_terminated_employee(employee_id: int, db: Session = Depends(get_db), user=Depends(require_permission("can_terminate"))):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    return reactivate_employee(db, e, user["email"])


@app.post("/api/v1/employees/{employee_id}/termination/preview")
def preview(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    return termination_preview(e)


@app.post("/api/v1/employees/{employee_id}/terminate")
def terminate_employee(employee_id: int, payload: TerminationRequest, db: Session = Depends(get_db), user=Depends(require_permission("can_terminate"))):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    result = terminate(db, e, user["email"], payload)
    # Send offboard confirmation email (non-blocking)
    try:
        from app.email import send_offboard_confirmation
        revoked = [a.platform for a in e.accounts if a.status != "active"]
        send_offboard_confirmation(user["email"], e.full_name, user["email"], revoked)
    except Exception:
        pass
    return result


@app.get("/api/v1/employees/{employee_id}/termination-report")
def termination_report(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    run = db.scalar(select(TerminationRun).where(TerminationRun.employee_id == employee_id).order_by(TerminationRun.created_at.desc()))
    return {
        "employee": employee_detail(e),
        "latest_termination": None if not run else {
            "id": run.id, "actor": run.actor, "effective_at": run.effective_at,
            "status": run.status, "summary": json.loads(run.summary_json), "created_at": run.created_at,
        },
        "accounts": [serialize_account(a) for a in e.accounts],
    }


# ── Assets ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/employees/{employee_id}/assets")
def assets(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Clinician not found")
    return [{"id": x.id, "asset_type": x.asset_type, "provider": x.provider,
             "identifier": x.identifier, "status": x.status,
             "metadata": json.loads(x.metadata_json or "{}"), "assigned_to": x.assigned_to}
            for x in db.scalars(select(CompanyAsset).where(CompanyAsset.employee_id == employee_id)).all()]


@app.post("/api/v1/assets/{asset_id}/freeze")
def freeze_asset(asset_id: int, db: Session = Depends(get_db), user=Depends(require_permission("can_revoke_access"))):
    x = db.get(CompanyAsset, asset_id)
    if not x:
        raise HTTPException(404, "Asset not found")
    x.status = "frozen"
    db.commit()
    audit(db, x.employee_id, user["email"], "freeze_asset", x.identifier, "verified", x.provider)
    return {"id": x.id, "status": x.status}


@app.post("/api/v1/assets/{asset_id}/transfer")
def transfer_asset(asset_id: int, payload: AssetTransferRequest, db: Session = Depends(get_db), user=Depends(require_auth)):
    x = db.get(CompanyAsset, asset_id)
    if not x:
        raise HTTPException(404, "Asset not found")
    x.assigned_to = payload.assigned_to
    x.status = "transferred"
    db.commit()
    audit(db, x.employee_id, user["email"], "transfer_asset", x.identifier, "completed", payload.assigned_to)
    return {"id": x.id, "status": x.status, "assigned_to": x.assigned_to}


# ── Audit Events ───────────────────────────────────────────────────────────────

@app.get("/api/v1/employees/{employee_id}/audit-events")
def audit_events(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    if not db.get(Employee, employee_id):
        raise HTTPException(404, "Clinician not found")
    rows = db.scalars(
        select(AuditEvent).where(AuditEvent.employee_id == employee_id).order_by(AuditEvent.created_at.desc())
    ).all()
    return [{"id": r.id, "actor": r.actor, "action": r.action, "target": r.target,
             "result": r.result, "detail": r.detail, "created_at": r.created_at} for r in rows]


@app.get("/api/v1/employees/{employee_id}/audit-events/export")
def export_audit_events(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e:
        raise HTTPException(404, "Clinician not found")
    rows = db.scalars(
        select(AuditEvent).where(AuditEvent.employee_id == employee_id).order_by(AuditEvent.created_at.desc())
    ).all()
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date (UTC)", "Actor", "Action", "Target", "Result", "Detail"])
    for r in rows:
        writer.writerow([r.created_at.isoformat(), r.actor, r.action, r.target, r.result, r.detail])
    slug = e.full_name.lower().replace(" ", "-")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="audit-{slug}.csv"'},
    )


# ── Gary (AI Agent) — blocking run ───────────────────────────────────────────

@app.post("/api/v1/agent/run", response_model=AgentRunResponse)
def run_gary_agent(payload: AgentRunRequest, db: Session = Depends(get_db), user=Depends(require_auth)):
    return run_agent(db, instruction=payload.instruction, auto_execute=payload.auto_execute, actor=user["email"])


# ── Gary (AI Agent) — SSE streaming run ──────────────────────────────────────

@app.post("/api/v1/agent/stream")
async def stream_gary_agent(
    payload: AgentRunRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    import asyncio

    from app.security import decode_access_token

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token_payload = decode_access_token(authorization.removeprefix("Bearer "))
    if not token_payload:
        raise HTTPException(401, "Invalid token")
    actor_user = db.scalar(select(User).where(User.id == int(token_payload["sub"])))
    if not actor_user or not actor_user.is_active:
        raise HTTPException(401, "User not found")

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def emit(step):
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "step", "step": step.model_dump(mode="json")},
        )

    # Set the emitter in the current context, then copy context for the thread
    tok = step_emitter.set(emit)
    ctx = contextvars.copy_context()
    step_emitter.reset(tok)  # reset in this coroutine; thread sees it via ctx

    instruction = payload.instruction
    auto_execute = payload.auto_execute
    actor_email = actor_user.email

    def run_sync():
        try:
            result = run_agent(db, instruction, auto_execute, actor=actor_email)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "done", "result": result.model_dump(mode="json")},
            )
        except Exception as exc:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "message": str(exc)},
            )

    async def event_stream():
        future = loop.run_in_executor(None, ctx.run, run_sync)
        try:
            while True:
                item = await asyncio.wait_for(queue.get(), timeout=120.0)
                yield f"data: {json.dumps(item)}\n\n"
                if item["type"] in ("done", "error"):
                    break
        except asyncio.TimeoutError:
            yield 'data: {"type":"error","message":"timeout"}\n\n'
        await future

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
