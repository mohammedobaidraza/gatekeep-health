import json
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import require_auth, require_permission
from app.config import settings
from app.db import Base, engine, get_db
from app.models import AuditEvent, CompanyAsset, Employee, EmployeeAccount, TerminationRun
from app.schemas import (AccountCreate, AssetTransferRequest, EmployeeCreate,
                         EmployeePatch, LoginRequest, RevokeRequest, TerminationRequest)
from app.services import (ACCESS_TEMPLATES, add_account, audit, auto_provision,
                          employee_detail, employee_summary, reactivate_employee,
                          reset_demo, restore_account, revoke_account,
                          serialize_account, terminate, termination_preview, utcnow)
from app.agent.orchestrator import run_agent
from app.agent.schemas import AgentRunRequest, AgentRunResponse
from app.auth import authenticate

Base.metadata.create_all(bind=engine)

app = FastAPI(title='GateKeep Health API', version='3.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
def landing():
    return {
        'name': 'GateKeep Health',
        'tagline': 'Clinical access management — every credential controlled, every departure secured.',
        'login_url': '/api/v1/auth/login',
        'docs': '/docs',
    }


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'gatekeep-health', 'version': '3.0.0'}


@app.post('/api/v1/auth/login')
def login(payload: LoginRequest):
    user = authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(401, 'Invalid email or password')
    return {
        'access_token': user['token'],
        'token_type': 'bearer',
        'user': {
            'email': user['email'],
            'name': user['name'],
            'role': user['role'],
        },
    }


@app.get('/api/v1/auth/me')
def me(user=Depends(require_auth)):
    return user


@app.post('/api/v1/demo/reset')
def demo_reset(db: Session = Depends(get_db)):
    reset_demo(db)
    return {'status': 'reset', 'staff': 3}


@app.get('/api/v1/access-templates')
def list_access_templates(user=Depends(require_auth)):
    return [
        {
            'key': key,
            'name': template['name'],
            'department': template['department'],
            'description': template['description'],
            'accounts': template['accounts'],
        }
        for key, template in ACCESS_TEMPLATES.items()
    ]


# ── Staff (Employees) ──────────────────────────────────────────────────────────

@app.get('/api/v1/employees')
def list_employees(db: Session = Depends(get_db), user=Depends(require_auth)):
    return [employee_summary(e) for e in db.scalars(select(Employee).order_by(Employee.full_name)).all()]


@app.post('/api/v1/employees')
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db), user=Depends(require_permission("can_create"))):
    if db.scalar(select(Employee).where(Employee.company_email == str(payload.company_email))):
        raise HTTPException(409, 'Company email already exists')

    # Base HIPAA risk score by department
    dept = payload.department.lower()
    base_risk = 75 if any(kw in dept for kw in ['medicine', 'surgery', 'icu', 'emergency']) else \
                65 if any(kw in dept for kw in ['pharmacy', 'nursing']) else \
                55 if any(kw in dept for kw in ['radiology', 'imaging']) else \
                45 if 'it' in dept or 'security' in dept else 35

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
    db.add(e); db.commit(); db.refresh(e)
    add_account(db, e, 'Staff Directory', e.company_email, 'Employee', 'low', 'directory', sessions=0)

    if payload.auto_provision:
        try:
            auto_provision(db, e, payload.access_template)
        except ValueError as error:
            raise HTTPException(400, str(error))

    audit(db, e.id, user['email'], 'credential_clinician', e.company_email, 'completed',
          'Clinical staff record and system access provisioned')
    return employee_detail(e)


@app.get('/api/v1/employees/{employee_id}')
def get_employee(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, 'Clinician not found')
    return employee_detail(e)


@app.patch('/api/v1/employees/{employee_id}')
def patch_employee(employee_id: int, payload: EmployeePatch, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, 'Clinician not found')
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    e.updated_at = utcnow(); db.commit()
    audit(db, e.id, user['email'], 'update_clinician', e.company_email, 'completed',
          json.dumps(payload.model_dump(exclude_unset=True), default=str))
    return employee_detail(e)


# ── Accounts ───────────────────────────────────────────────────────────────────

@app.get('/api/v1/employees/{employee_id}/accounts')
def employee_accounts(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    if not db.get(Employee, employee_id): raise HTTPException(404, 'Clinician not found')
    return [serialize_account(a) for a in db.scalars(
        select(EmployeeAccount).where(EmployeeAccount.employee_id == employee_id).order_by(EmployeeAccount.platform)
    ).all()]


@app.post('/api/v1/employees/{employee_id}/accounts')
def create_account(employee_id: int, payload: AccountCreate, db: Session = Depends(get_db), user=Depends(require_permission("can_create"))):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, 'Clinician not found')
    a = add_account(db, e, payload.platform, payload.identifier, payload.access_level,
                    payload.risk_level, payload.account_type, payload.metadata,
                    payload.session_count, payload.credentials)
    db.commit()
    audit(db, e.id, user['email'], 'add_account', payload.platform, 'completed', payload.identifier)
    return serialize_account(a)


@app.post('/api/v1/accounts/{account_id}/revoke')
def account_revoke(account_id: int, payload: RevokeRequest, db: Session = Depends(get_db), user=Depends(require_permission("can_revoke_access"))):
    a = db.get(EmployeeAccount, account_id)
    if not a: raise HTTPException(404, 'Account not found')
    return revoke_account(db, a, user['email'], payload.reason, payload.action)


@app.post('/api/v1/accounts/{account_id}/restore')
def account_restore(account_id: int, db: Session = Depends(get_db), user=Depends(require_permission("can_revoke_access"))):
    a = db.get(EmployeeAccount, account_id)
    if not a: raise HTTPException(404, 'Account not found')
    if a.status == 'active': raise HTTPException(400, 'Account is already active')
    restored = restore_account(db, a, user['email'])
    return {**restored, 'sessions_restored': False, 'credentials_restored': False,
            'message': 'Account restored. Previous sessions and credentials remain revoked.'}


@app.post('/api/v1/accounts/{account_id}/verify')
def account_verify(account_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    a = db.get(EmployeeAccount, account_id)
    if not a: raise HTTPException(404, 'Account not found')
    remaining_sessions = any(s.active for s in a.sessions)
    remaining_credentials = any(c.status == 'active' for c in a.credentials)
    verified = a.status in {'revoked', 'frozen', 'cancelled', 'disabled'} and not remaining_sessions and not remaining_credentials
    a.revocation_verified = verified; db.commit()
    audit(db, a.employee_id, user['email'], 'verify_account', a.platform,
          'verified' if verified else 'failed', a.identifier)
    return {'account_id': a.id, 'verified': verified, 'status': a.status,
            'remaining_sessions': remaining_sessions, 'remaining_credentials': remaining_credentials}


# ── Reactivate / Terminate ─────────────────────────────────────────────────────

@app.post('/api/v1/employees/{employee_id}/reactivate')
def reactivate_terminated_employee(employee_id: int, db: Session = Depends(get_db), user=Depends(require_permission("can_terminate"))):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, 'Clinician not found')
    return reactivate_employee(db, e, user['email'])


@app.post('/api/v1/employees/{employee_id}/termination/preview')
def preview(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, 'Clinician not found')
    return termination_preview(e)


@app.post('/api/v1/employees/{employee_id}/terminate')
def terminate_employee(employee_id: int, payload: TerminationRequest, db: Session = Depends(get_db), user=Depends(require_permission("can_terminate"))):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, 'Clinician not found')
    return terminate(db, e, user['email'], payload)


@app.get('/api/v1/employees/{employee_id}/termination-report')
def termination_report(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    e = db.get(Employee, employee_id)
    if not e: raise HTTPException(404, 'Clinician not found')
    run = db.scalar(select(TerminationRun).where(TerminationRun.employee_id == employee_id).order_by(TerminationRun.created_at.desc()))
    return {
        'employee': employee_detail(e),
        'latest_termination': None if not run else {
            'id': run.id, 'actor': run.actor, 'effective_at': run.effective_at,
            'status': run.status, 'summary': json.loads(run.summary_json), 'created_at': run.created_at,
        },
        'accounts': [serialize_account(a) for a in e.accounts],
    }


# ── Assets ─────────────────────────────────────────────────────────────────────

@app.get('/api/v1/employees/{employee_id}/assets')
def assets(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    if not db.get(Employee, employee_id): raise HTTPException(404, 'Clinician not found')
    return [{'id': x.id, 'asset_type': x.asset_type, 'provider': x.provider,
             'identifier': x.identifier, 'status': x.status,
             'metadata': json.loads(x.metadata_json or '{}'), 'assigned_to': x.assigned_to}
            for x in db.scalars(select(CompanyAsset).where(CompanyAsset.employee_id == employee_id)).all()]


@app.post('/api/v1/assets/{asset_id}/freeze')
def freeze_asset(asset_id: int, db: Session = Depends(get_db), user=Depends(require_permission("can_revoke_access"))):
    x = db.get(CompanyAsset, asset_id)
    if not x: raise HTTPException(404, 'Asset not found')
    x.status = 'frozen'; db.commit()
    audit(db, x.employee_id, user['email'], 'freeze_asset', x.identifier, 'verified', x.provider)
    return {'id': x.id, 'status': x.status}


@app.post('/api/v1/assets/{asset_id}/transfer')
def transfer_asset(asset_id: int, payload: AssetTransferRequest, db: Session = Depends(get_db), user=Depends(require_auth)):
    x = db.get(CompanyAsset, asset_id)
    if not x: raise HTTPException(404, 'Asset not found')
    x.assigned_to = payload.assigned_to; x.status = 'transferred'; db.commit()
    audit(db, x.employee_id, user['email'], 'transfer_asset', x.identifier, 'completed', payload.assigned_to)
    return {'id': x.id, 'status': x.status, 'assigned_to': x.assigned_to}


@app.get('/api/v1/employees/{employee_id}/audit-events')
def audit_events(employee_id: int, db: Session = Depends(get_db), user=Depends(require_auth)):
    if not db.get(Employee, employee_id): raise HTTPException(404, 'Clinician not found')
    rows = db.scalars(select(AuditEvent).where(AuditEvent.employee_id == employee_id).order_by(AuditEvent.created_at.desc())).all()
    return [{'id': r.id, 'actor': r.actor, 'action': r.action, 'target': r.target,
             'result': r.result, 'detail': r.detail, 'created_at': r.created_at} for r in rows]


# ── Grace (AI Agent) ───────────────────────────────────────────────────────────

@app.post('/api/v1/agent/run', response_model=AgentRunResponse)
def run_grace_agent(payload: AgentRunRequest, db: Session = Depends(get_db), user=Depends(require_auth)):
    return run_agent(db, instruction=payload.instruction, auto_execute=payload.auto_execute, actor=user['email'])
