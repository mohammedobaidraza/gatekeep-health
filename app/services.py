import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import AccountSession, AuditEvent, CompanyAsset, Credential, Employee, EmployeeAccount, TerminationRun


def utcnow(): return datetime.now(timezone.utc)


def audit(db: Session, employee_id: int | None, actor: str, action: str, target: str, result: str, detail: str = ""):
    db.add(AuditEvent(employee_id=employee_id, actor=actor, action=action, target=target, result=result, detail=detail))
    db.commit()


def add_account(db: Session, employee: Employee, platform: str, identifier: str, access: str = "standard", risk: str = "low", account_type: str = "clinical_system", metadata: dict | None = None, sessions: int = 1, credentials: list[str] | None = None):
    a = EmployeeAccount(
        employee_id=employee.id,
        platform=platform,
        account_type=account_type,
        identifier=identifier,
        access_level=access,
        status="active",
        last_used_at=utcnow() - timedelta(hours=3),
        risk_level=risk,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(a); db.flush()
    for i in range(sessions):
        db.add(AccountSession(
            employee_account_id=a.id,
            session_type="workstation" if i == 0 else "mobile",
            active=True,
            last_seen_at=utcnow() - timedelta(minutes=15 + i * 20),
        ))
    for c in credentials or []:
        db.add(Credential(employee_account_id=a.id, credential_type=c, status="active", metadata_json="{}"))
    return a


ACCESS_TEMPLATES = {
    "physician": {
        "name": "Physician (MD/DO)",
        "department": "Clinical Medicine",
        "description": "Epic attending access, PACS imaging, e-prescribing with DEA, care coordination, and telemedicine.",
        "accounts": [
            {"platform": "Epic EMR", "access": "Attending Physician", "risk": "critical", "sessions": 2, "credentials": ["Smart card", "RSA token"]},
            {"platform": "PACS (Imaging)", "access": "Radiologist View", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "eRx / Surescripts", "access": "Prescriber", "risk": "critical", "sessions": 1, "credentials": ["DEA certificate"]},
            {"platform": "Care Coordination Portal", "access": "Attending", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "Telemedicine Platform", "access": "Provider", "risk": "medium", "sessions": 1, "credentials": []},
            {"platform": "Clinical Decision Support", "access": "Standard", "risk": "low", "sessions": 1, "credentials": []},
        ],
    },
    "nurse": {
        "name": "Registered Nurse (RN)",
        "department": "Clinical Nursing",
        "description": "Epic nursing module, medication administration record, PYXIS dispensing, patient monitoring, and care communication.",
        "accounts": [
            {"platform": "Epic EMR", "access": "RN Nursing", "risk": "high", "sessions": 2, "credentials": ["Smart card"]},
            {"platform": "MAR (Medication Admin)", "access": "Nurse", "risk": "critical", "sessions": 1, "credentials": ["Badge scan"]},
            {"platform": "Patient Monitoring", "access": "Bedside RN", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "PYXIS (Medication Dispense)", "access": "RN Access", "risk": "high", "sessions": 1, "credentials": ["Fingerprint"]},
            {"platform": "Care Communication", "access": "Staff", "risk": "low", "sessions": 2, "credentials": []},
        ],
    },
    "pharmacist": {
        "name": "Pharmacist (PharmD)",
        "department": "Pharmacy",
        "description": "Pharmacy management system, PYXIS admin, controlled substance tracking, DEA integration, and drug interaction database.",
        "accounts": [
            {"platform": "Pharmacy Management System", "access": "Staff Pharmacist", "risk": "critical", "sessions": 2, "credentials": ["Smart card"]},
            {"platform": "PYXIS (Medication Dispense)", "access": "Admin", "risk": "critical", "sessions": 1, "credentials": ["Smart card"]},
            {"platform": "Controlled Substance Monitor", "access": "Pharmacist", "risk": "critical", "sessions": 1, "credentials": ["DEA certificate"]},
            {"platform": "Epic EMR", "access": "Pharmacy", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "Drug Interaction Database", "access": "Standard", "risk": "low", "sessions": 1, "credentials": []},
        ],
    },
    "radiology_tech": {
        "name": "Radiology Technician (RT)",
        "department": "Radiology",
        "description": "PACS, RIS, imaging workstations, radiation safety tracking, and scheduling.",
        "accounts": [
            {"platform": "PACS (Imaging)", "access": "RT Technician", "risk": "high", "sessions": 2, "credentials": ["Smart card"]},
            {"platform": "RIS (Radiology Info System)", "access": "Technologist", "risk": "medium", "sessions": 1, "credentials": []},
            {"platform": "Radiation Safety Tracking", "access": "Staff", "risk": "medium", "sessions": 1, "credentials": ["Dosimeter ID"]},
            {"platform": "Epic EMR", "access": "Radiology", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "Modality Workstation", "access": "Operator", "risk": "medium", "sessions": 1, "credentials": []},
        ],
    },
    "medical_admin": {
        "name": "Medical Administrator",
        "department": "Administration",
        "description": "Epic billing and registration, insurance portals, scheduling, and revenue cycle management.",
        "accounts": [
            {"platform": "Epic EMR", "access": "Registration/Billing", "risk": "high", "sessions": 2, "credentials": []},
            {"platform": "Insurance Portal", "access": "Claims Processor", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "Scheduling System", "access": "Scheduler", "risk": "medium", "sessions": 1, "credentials": []},
            {"platform": "Revenue Cycle Management", "access": "Coder", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "Microsoft 365", "access": "Standard", "risk": "low", "sessions": 1, "credentials": []},
        ],
    },
    "it_security": {
        "name": "IT / Security (Healthcare)",
        "department": "Information Technology",
        "description": "Clinical system administration, HIPAA audit tools, network infrastructure, IAM, and security monitoring.",
        "accounts": [
            {"platform": "Epic EMR", "access": "Technical Admin", "risk": "critical", "sessions": 1, "credentials": ["Smart card", "RSA token"]},
            {"platform": "HIPAA Audit System", "access": "Auditor", "risk": "critical", "sessions": 1, "credentials": []},
            {"platform": "Network Infrastructure", "access": "Admin", "risk": "critical", "sessions": 1, "credentials": ["VPN certificate"]},
            {"platform": "Identity Management (IAM)", "access": "Admin", "risk": "critical", "sessions": 1, "credentials": ["Service account"]},
            {"platform": "Security Monitoring (SIEM)", "access": "Analyst", "risk": "high", "sessions": 1, "credentials": []},
            {"platform": "Cloud Health Platform", "access": "Admin", "risk": "critical", "sessions": 1, "credentials": ["Access key"]},
        ],
    },
}


def infer_access_template(employee: Employee) -> str:
    dept = employee.department.lower()
    title = employee.job_title.lower()

    if any(kw in title for kw in ["physician", "doctor", " md", " do", "attending", "surgeon", "hospitalist"]):
        return "physician"
    if any(kw in dept for kw in ["pharmacy", "pharmacist"]) or "pharmacist" in title:
        return "pharmacist"
    if "radiology" in dept or "imaging" in dept or any(kw in title for kw in ["radiolog", "x-ray", "mri", "ct tech"]):
        return "radiology_tech"
    if any(kw in title for kw in ["nurse", " rn", " lpn", " np", "nursing"]):
        return "nurse"
    if any(kw in dept for kw in ["information technology", " it ", "security"]) or any(kw in title for kw in ["it admin", "sysadmin", "security analyst"]):
        return "it_security"
    if any(kw in dept for kw in ["admin", "billing", "finance", "scheduling"]) or any(kw in title for kw in ["admin", "coordinator", "scheduler", "coder"]):
        return "medical_admin"
    return "nurse"


def auto_provision(db: Session, employee: Employee, template_key: str | None = None):
    selected_key = template_key or infer_access_template(employee)
    template = ACCESS_TEMPLATES.get(selected_key)
    if not template:
        raise ValueError(f"Unknown access template: {selected_key}")

    local = employee.company_email.split("@")[0]
    created = []

    for defn in template["accounts"]:
        platform = defn["platform"]
        if platform == "Microsoft 365":
            identifier = employee.company_email
        elif platform in {"eRx / Surescripts", "Controlled Substance Monitor"}:
            identifier = employee.dea_number or local
        elif platform in {"Epic EMR", "MAR (Medication Admin)", "Pharmacy Management System",
                          "PYXIS (Medication Dispense)", "PACS (Imaging)", "RIS (Radiology Info System)",
                          "HIPAA Audit System", "Identity Management (IAM)"}:
            identifier = local
        else:
            identifier = local.replace(".", "-")

        account = add_account(
            db, employee, platform, identifier,
            defn["access"], defn["risk"],
            sessions=defn["sessions"],
            credentials=defn["credentials"],
        )
        created.append(account)

    db.commit()
    return created


def serialize_account(a: EmployeeAccount):
    return {
        'id': a.id, 'employee_id': a.employee_id, 'platform': a.platform,
        'account_type': a.account_type, 'identifier': a.identifier,
        'access_level': a.access_level, 'status': a.status, 'last_used_at': a.last_used_at,
        'risk_level': a.risk_level, 'external_account_id': a.external_account_id,
        'metadata': json.loads(a.metadata_json or '{}'),
        'revocation_verified': a.revocation_verified,
        'active_sessions': sum(1 for s in a.sessions if s.active),
        'active_credentials': sum(1 for c in a.credentials if c.status == 'active'),
    }


def employee_summary(e: Employee):
    accounts = len(e.accounts)
    active = sum(1 for a in e.accounts if a.status == 'active')
    risk = 'High' if e.risk_score >= 70 else 'Medium' if e.risk_score >= 40 else 'Low'
    return {
        'id': e.id, 'full_name': e.full_name, 'company_email': e.company_email,
        'department': e.department, 'job_title': e.job_title, 'manager_name': e.manager_name,
        'employment_status': e.employment_status, 'accounts_count': accounts,
        'active_accounts': active, 'risk_score': e.risk_score, 'risk_level': risk,
        # Healthcare summary fields
        'npi_number': e.npi_number, 'license_type': e.license_type,
        'privilege_level': e.privilege_level, 'credential_expiry': e.credential_expiry,
    }


def employee_detail(e: Employee):
    sessions = sum(1 for a in e.accounts for s in a.sessions if s.active)
    creds = sum(1 for a in e.accounts for c in a.credentials if c.status == 'active')
    groups = sum(len(json.loads(a.metadata_json or '{}').get('groups', [])) for a in e.accounts)
    return {
        **employee_summary(e),
        'personal_email': e.personal_email, 'start_date': e.start_date,
        'termination_date': e.termination_date, 'last_access_review': e.last_access_review,
        'active_sessions': sessions, 'active_credentials': creds,
        'group_memberships': groups, 'owned_assets': len(e.assets),
        'created_at': e.created_at, 'updated_at': e.updated_at,
        # Healthcare detail fields
        'license_number': e.license_number, 'license_state': e.license_state,
        'dea_number': e.dea_number,
    }


def revoke_account(db: Session, a: EmployeeAccount, actor: str, reason: str, requested_action: str | None = None):
    now = utcnow()
    action = requested_action or ('freeze' if a.account_type == 'company_card' or 'card' in a.platform.lower() else 'revoke')
    for s in a.sessions:
        if s.active: s.active = False; s.revoked_at = now
    for c in a.credentials:
        if c.status == 'active': c.status = 'revoked'; c.revoked_at = now
    a.status = 'frozen' if action == 'freeze' else 'cancelled' if action == 'cancel' else 'revoked'
    a.revocation_verified = True; a.updated_at = now; db.commit()
    audit(db, a.employee_id, actor, f'{action}_account', a.platform, 'verified', f'{reason}; identifier={a.identifier}')
    return serialize_account(a)


def restore_account(db: Session, a: EmployeeAccount, actor: str, reason: str = "Accidental revocation"):
    if a.status == "active":
        return serialize_account(a)
    a.status = "active"
    a.revocation_verified = False
    a.updated_at = utcnow()
    db.commit()
    audit(db, a.employee_id, actor, "restore_account", a.platform, "completed",
          f"{reason}; identifier={a.identifier}; old sessions and credentials remain revoked")
    return serialize_account(a)


def reactivate_employee(db: Session, e: Employee, actor: str):
    if e.employment_status == "active":
        return {"status": "already_active", "employee": employee_detail(e), "accounts_restored": 0}

    restored_count = 0
    for account in e.accounts:
        if account.status != "active":
            restore_account(db, account, actor, "Clinician re-credentialed")
            restored_count += 1

    for asset in e.assets:
        if asset.asset_type == "company_card" and asset.status == "frozen":
            asset.status = "active"
        if asset.asset_type != "company_card":
            asset.assigned_to = None

    e.employment_status = "active"
    e.termination_date = None
    e.updated_at = utcnow()
    db.commit(); db.refresh(e)

    audit(db, e.id, actor, "reactivate_employee", e.company_email, "completed",
          f"Restored {restored_count} clinical system accounts; old sessions and credentials remain revoked")

    return {
        "status": "reactivated",
        "employee": employee_detail(e),
        "accounts_restored": restored_count,
        "sessions_restored": False,
        "credentials_restored": False,
        "message": "Clinician re-credentialed. Accounts restored; old sessions and credentials remain revoked.",
    }


def termination_preview(e: Employee):
    active = [a for a in e.accounts if a.status == 'active']
    return {
        'employee_id': e.id, 'employee': e.full_name,
        'accounts_discovered': len(active),
        'active_sessions': sum(1 for a in active for s in a.sessions if s.active),
        'active_credentials': sum(1 for a in active for c in a.credentials if c.status == 'active'),
        'company_cards': sum(1 for x in e.assets if x.asset_type == 'company_card' and x.status == 'active'),
        'owned_assets': len(e.assets),
        'actions': [{'account_id': a.id, 'platform': a.platform, 'identifier': a.identifier,
                     'planned_action': 'freeze' if a.account_type == 'company_card' else 'revoke'} for a in active],
    }


def terminate(db: Session, e: Employee, actor: str, req):
    now = utcnow(); effective = req.effective_at or now
    if effective > now:
        e.employment_status = 'termination_scheduled'; e.termination_date = effective; db.commit()
        audit(db, e.id, actor, 'schedule_offboarding', e.company_email, 'scheduled', effective.isoformat())
        return {'status': 'scheduled', 'effective_at': effective}

    preview = termination_preview(e); revoked = verified = manual = cards = 0
    for a in e.accounts:
        if a.status != 'active': continue
        revoke_account(db, a, actor, 'Secure clinician offboarding', 'revoke')
        revoked += 1; verified += int(a.revocation_verified)

    if req.freeze_company_card:
        for asset in e.assets:
            if asset.asset_type == 'company_card' and asset.status == 'active':
                asset.status = 'frozen'; cards += 1
                audit(db, e.id, actor, 'freeze_card', asset.identifier, 'verified', asset.provider)

    if req.transfer_files_to_manager and e.manager_name:
        for asset in e.assets:
            if asset.asset_type != 'company_card': asset.assigned_to = e.manager_name

    e.employment_status = 'terminated'; e.termination_date = effective; e.updated_at = now
    summary = {
        'accounts_discovered': preview['accounts_discovered'],
        'accounts_revoked': revoked,
        'accounts_verified': verified,
        'requires_manual_action': manual,
        'sessions_terminated': preview['active_sessions'],
        'tokens_revoked': preview['active_credentials'],
        'company_cards_frozen': cards,
        'files_transferred': 143 if req.transfer_files_to_manager else 0,
        'hidden_access_discovered': sum(1 for a in e.accounts for c in a.credentials if c.credential_type in {'DEA certificate', 'Smart card', 'RSA token'}),
    }
    run = TerminationRun(employee_id=e.id, actor=actor, effective_at=effective, status='completed', summary_json=json.dumps(summary))
    db.add(run); db.commit()
    audit(db, e.id, actor, 'offboard_clinician', e.company_email, 'completed', json.dumps(summary))
    return {'termination_id': run.id, 'status': 'completed', 'effective_at': effective, 'summary': summary}


def reset_demo(db: Session):
    from app.models import User
    from app.security import hash_password
    from app.config import settings

    for model in [TerminationRun, AuditEvent, Credential, AccountSession, CompanyAsset, EmployeeAccount, Employee, User]:
        db.query(model).delete()
    db.commit()

    # Seed the four demo system users with real bcrypt hashes
    for u in [
        {"email": settings.demo_admin_email,      "name": "System Administrator", "password": settings.demo_admin_password,      "role": "system_admin"},
        {"email": settings.demo_head_email,        "name": "Department Head",      "password": settings.demo_head_password,        "role": "department_head"},
        {"email": settings.demo_coordinator_email, "name": "Staff Coordinator",    "password": settings.demo_coordinator_password, "role": "staff_coordinator"},
        {"email": settings.demo_compliance_email,  "name": "Compliance Officer",   "password": settings.demo_compliance_password,  "role": "compliance_officer"},
    ]:
        db.add(User(email=u["email"], name=u["name"], hashed_password=hash_password(u["password"]), role=u["role"], is_active=True))
    db.commit()

    # Dr. Sarah Chen — Attending Physician (critical access, high HIPAA risk)
    sarah = Employee(
        full_name='Dr. Sarah Chen',
        company_email='sarah.chen@cityhealth.org',
        personal_email='sarah.personal@example.com',
        department='Clinical Medicine',
        job_title='Attending Physician',
        manager_name='Dr. Michael Roberts',
        employment_status='active',
        start_date=datetime(2022, 3, 4).date(),
        risk_score=92,
        last_access_review=utcnow() - timedelta(days=89),
        npi_number='1234567890',
        license_number='MD-CA-12345',
        license_state='CA',
        license_type='MD',
        dea_number='BC1234563',
        privilege_level='full',
        credential_expiry=datetime(2026, 6, 30).date(),
    )
    db.add(sarah); db.flush()
    add_account(db, sarah, 'Epic EMR', 'sarah.chen', 'Attending Physician', 'critical', sessions=2, credentials=['Smart card', 'RSA token'])
    add_account(db, sarah, 'PACS (Imaging)', 'schen@cityhealth.org', 'Radiologist View', 'high', sessions=1)
    add_account(db, sarah, 'eRx / Surescripts', 'BC1234563', 'Prescriber', 'critical', sessions=1, credentials=['DEA certificate'])
    add_account(db, sarah, 'Care Coordination Portal', 'sarah.chen', 'Attending', 'high', sessions=1)
    add_account(db, sarah, 'Telemedicine Platform', 'sarah.chen@cityhealth.org', 'Provider', 'medium', sessions=1)
    add_account(db, sarah, 'Clinical Decision Support', 'sarah.chen', 'Standard', 'low', sessions=1)
    db.add(CompanyAsset(
        employee_id=sarah.id, asset_type='mobile_device', provider='Apple',
        identifier='iPhone GK-MED-019', status='assigned', metadata_json='{}',
    ))

    # James Torres — Registered Nurse (medium HIPAA risk)
    james = Employee(
        full_name='James Torres',
        company_email='james.torres@cityhealth.org',
        department='Clinical Nursing',
        job_title='Registered Nurse',
        manager_name='Charge Nurse Patricia Kim',
        employment_status='active',
        start_date=datetime(2024, 6, 15).date(),
        risk_score=52,
        last_access_review=utcnow() - timedelta(days=25),
        npi_number='9876543210',
        license_number='RN-CA-78901',
        license_state='CA',
        license_type='RN',
        privilege_level='standard',
        credential_expiry=datetime(2027, 1, 31).date(),
    )
    db.add(james); db.flush()
    auto_provision(db, james, template_key='nurse')

    # Dr. Fatima Al-Rashid — Staff Pharmacist (medium-high risk, DEA access)
    fatima = Employee(
        full_name='Dr. Fatima Al-Rashid',
        company_email='fatima.alrashid@cityhealth.org',
        department='Pharmacy',
        job_title='Staff Pharmacist',
        manager_name='Chief Pharmacist Dr. Chen',
        employment_status='active',
        start_date=datetime(2023, 9, 1).date(),
        risk_score=68,
        last_access_review=utcnow() - timedelta(days=14),
        license_number='PharmD-CA-55123',
        license_state='CA',
        license_type='PharmD',
        dea_number='FA9876541',
        privilege_level='full',
        credential_expiry=datetime(2025, 12, 31).date(),
    )
    db.add(fatima); db.flush()
    auto_provision(db, fatima, template_key='pharmacist')

    db.commit()
    audit(db, None, 'system', 'reset_demo', 'cityhealth.org', 'completed',
          'Created three synthetic healthcare staff members')
