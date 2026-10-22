# GateKeep Health — What We Built

**Date:** October 22, 2026
**Repo:** https://github.com/mohammedobaidraza/gatekeep-health
**Collaborator access granted to:** [@huda-code](https://github.com/huda-code)

---

## Starting Point

We forked **GateKeep** (https://github.com/huda-code/GateKeep) — a generic employee IAM demo — and transformed it end-to-end into **GateKeep Health**, a clinical staff identity and access management system purpose-built for healthcare organizations.

---

## What Changed

### 1. Branding & Identity

- Product renamed from **GateKeep** → **GateKeep Health** throughout the entire codebase
- Logo updated: "GateKeep **Health**" with subdued Health suffix
- Page title, meta description, and all in-app copy rewritten for a clinical context
- "Employees" → **Clinicians**, "Offboard" → **Offboard clinician**, "Gary" agent → **Grace**

---

### 2. Role-Based Access Control (RBAC)

Four healthcare roles implemented, each with a distinct permission set:

| Role | Can Create | Can Terminate | Can Revoke Access | Can Audit |
|------|-----------|--------------|-------------------|-----------|
| System Admin | Yes | Yes | Yes | Yes |
| Department Head | Yes | No | No | Yes |
| Staff Coordinator | Yes | No | No | No |
| Compliance Officer | No | No | Yes | Yes |

Every API endpoint is gated with a `require_permission("can_X")` FastAPI dependency. A department head hitting the terminate endpoint gets a clear 403:

```
"Your role ('department_head') does not have permission: can_terminate"
```

---

### 3. Healthcare Data Model

Seven new fields added to the clinician record:

| Field | Description |
|-------|-------------|
| `npi_number` | 10-digit National Provider Identifier |
| `license_number` | State medical license |
| `license_state` | 2-char state code (e.g. CA) |
| `license_type` | MD, DO, RN, LPN, NP, PA, PharmD, RT, DDS |
| `dea_number` | DEA registration (required for prescribers) |
| `privilege_level` | full / limited / supervised / standard |
| `credential_expiry` | License or privileging expiry date |

The dashboard surfaces credential expiry status — "expired" and "expiring soon" badges appear automatically when a clinician's license is within 90 days of or past expiry.

---

### 4. Clinical Access Templates

Six role-based provisioning templates replace the original generic ones. Selecting a template automatically provisions the correct clinical systems with the right access levels and credential requirements:

| Template | Systems Provisioned |
|----------|-------------------|
| **Physician** | Epic EMR (Attending), PACS, eRx/Surescripts (DEA), Care Coordination, Telemedicine, CDS |
| **Nurse** | Epic EMR (RN), Medication Administration Record, Patient Monitoring, PYXIS (fingerprint), Care Communication |
| **Pharmacist** | Pharmacy Management (smart card), PYXIS Admin, Controlled Substance Monitor (DEA), Epic, Drug Database |
| **Radiology Tech** | PACS, Radiology IS, Radiation Safety (dosimeter), Epic, Modality Workstation |
| **Medical Admin** | Epic Billing/Registration, Insurance Portal, Scheduling, Revenue Cycle, Microsoft 365 |
| **IT Security** | Epic Technical Admin (smart card + RSA), HIPAA Audit, Network Infrastructure, IAM, SIEM, Cloud Health Platform |

Risk levels range from `low` to `critical`. Systems requiring DEA certificates, smart cards, or biometrics are flagged appropriately.

---

### 5. Clinician Onboarding Form

The "Add clinician" page was completely rebuilt:

- Role template picker with system preview (shows every system that will be provisioned before you submit)
- NPI number field
- License number + state (side-by-side)
- License type pill picker: MD / DO / RN / LPN / NP / PA / PharmD / RT / DDS / Other
- DEA number field
- Privilege level selector: Full / Limited / Supervised / Standard (non-clinical)
- Credential expiry date
- Submit label: **"Credential and provision N systems"** — makes the action explicit

---

### 6. Grace (AI Agent)

The "Gary" AI agent was rebranded as **Grace** and updated with healthcare-specific examples:

- **Credentialing example:** "Add Dr. Layla Hassan as an attending physician. Her email is layla.hassan@cityhealth.org. Her supervisor is Dr. Michael Roberts."
- **Offboarding example:** "Offboard Nurse James Torres immediately. Revoke all clinical system access, preserve patient records per HIPAA, and notify the department head."

Grace resolves the clinician, builds an access plan, executes the workflow, verifies the result, and writes a structured report — all from plain-language instructions.

The agent offboarding actions were also updated to healthcare terminology:
- `preserve_records` (HIPAA patient record preservation)
- `notify_medical_staff_office`
- `revoke_dea_system_access`
- `revoke_prescribing_access`

---

### 7. Demo Login Accounts

Four pre-seeded accounts for instant demo access (click-to-fill on the login page):

| Role | Email | Password | Token |
|------|-------|----------|-------|
| System Admin | admin@health.demo | admin123 | ghk-admin-2026 |
| Department Head | head@health.demo | dept123 | ghk-head-2026 |
| Staff Coordinator | coordinator@health.demo | coord123 | ghk-coord-2026 |
| Compliance Officer | compliance@health.demo | comply123 | ghk-comply-2026 |

---

### 8. Demo Seed Data

Three clinicians pre-loaded to demo the full range of risk levels and clinical roles:

- **Dr. Sarah Chen** — MD, Cardiology, Attending Physician, HIPAA risk score 92 (critical)
- **James Torres** — RN, Emergency Department, Staff Nurse, HIPAA risk score 52 (medium)
- **Dr. Fatima Al-Rashid** — PharmD, Clinical Pharmacy, Pharmacist, HIPAA risk score 68 (high)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.115 + SQLAlchemy 2 + SQLite |
| AI Agent | Claude claude-sonnet-4-6 (via Anthropic SDK) |
| Frontend | Next.js 16 + TypeScript + Tailwind CSS |
| Auth | Token-based (localStorage), RBAC via FastAPI dependencies |
| Data Validation | Pydantic v2 + pydantic-settings |

---

## Running Locally

```bash
# Backend
cd gatekeep-health
python3 -m pip install fastapi uvicorn[standard] sqlalchemy pydantic-settings email-validator anthropic
uvicorn app.main:app --reload
# → http://localhost:8000

# Seed demo data
curl -X POST http://localhost:8000/demo/reset

# Frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

---

## Files Changed vs Original GateKeep

| File | What Changed |
|------|-------------|
| `app/config.py` | 4 healthcare demo user configs |
| `app/auth.py` | Full RBAC system with 4 roles and 6 permissions |
| `app/models.py` | 7 new healthcare fields on Employee |
| `app/schemas.py` | Healthcare fields in Create/Patch; healthcare offboarding flags |
| `app/services.py` | 6 clinical access templates replacing generic ones |
| `app/main.py` | Permission-gated endpoints; healthcare API title |
| `app/agent/schemas.py` | Healthcare access templates; healthcare offboarding actions |
| `frontend/app/layout.tsx` | "GateKeep Health" title and meta |
| `frontend/components/ui/Logo.tsx` | "Health" suffix in logo |
| `frontend/lib/api.ts` | Healthcare fields in all types; AuthUser with role |
| `frontend/app/login/page.tsx` | 4 demo accounts panel; clinical branding |
| `frontend/app/dashboard/page.tsx` | Clinical columns: License, Credential Status, HIPAA Risk |
| `frontend/app/employees/new/page.tsx` | Full healthcare onboarding form |
| `frontend/app/employees/[id]/page.tsx` | Licensure block; healthcare stat labels |
| `frontend/app/gary/page.tsx` | Gary → Grace; healthcare examples |
| `.env.example` | 4 demo user credential sets |
