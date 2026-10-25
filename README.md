# GateKeep

**One employee out. Every access path closed.**

GateKeep is an AI-assisted employee identity lifecycle platform for onboarding, access provisioning, and secure offboarding.

Its built-in agent, **Gary**, accepts a natural-language request, identifies whether the request is onboarding or offboarding, creates an execution plan, performs the workflow, verifies the final state, and produces proof of completion.

## The problem

Employee onboarding and offboarding are often handled through tickets, spreadsheets, Slack messages, and manual checklists.

For onboarding, IT teams must:

- Create the employee record
- Determine access based on role
- Provision accounts across multiple platforms
- Confirm that each account was created correctly

For offboarding, they must:

- Find every account owned by the employee
- Revoke application access
- Terminate active sessions
- Revoke credentials and API tokens
- Freeze company cards
- Transfer company assets
- Verify that no access remains
- Produce an audit record

A single missed account or credential can become a serious security and compliance risk.

GateKeep automates this process end to end.

## Gary, the GateKeep agent

Gary allows an administrator to paste a plain-English instruction and run the complete workflow with one click.

### Onboarding example

```text
Onboard Dr. Layla Hassan as a cardiologist.
Her email is layla.hassan@cityhealth.org.
Her supervisor is Dr. Michael Roberts.
```

Gary resolves the role, builds the access plan, provisions every account, verifies the final state, and writes a proof-of-work report — then an animated panel shows each system being granted in real time.

### Offboarding example

```text
Offboard Nurse James Torres immediately.
Revoke all clinical system access, preserve patient records per HIPAA,
and notify the department head.
```

## Roles & access templates

Each role is provisioned with **5–6 role-specific clinical applications**, plus a common baseline every staff member receives: **Google Workspace** (domain), **Shared Drive — Employee Handbook**, **Shared Drive — EMR Training**, and **Rippling (HRIS)**.

| Role | Key | Representative applications |
|------|-----|----------------------------|
| Physician (MD/DO) | `physician` | Epic EMR, PACS, eRx/Surescripts, Care Coordination, Telemedicine, Clinical Decision Support |
| Cardiologist | `cardiologist` | Epic (Cardiology), Philips Xcelera (Echo), GE Mac-Lab (Cath Lab), GE MUSE (ECG), CVIS, eRx/Surescripts |
| Medical Director | `medical_director` | Epic (Executive), Clinical Quality Dashboard, symplr Credentialing, Peer Review, Formulary Oversight, Incident & Risk (RL6) |
| Clinical Case Manager (RN) | `case_manager` | Epic Case Management, InterQual/MCG, Discharge Planning, Care Coordination, Payer Authorization, Social Services Referral |
| Clinical Nurse Manager (RN) | `clinical_nurse_manager` | Epic (Nursing Admin), UKG/Kronos Scheduling, MAR Oversight, Patient Acuity, Incident Reporting (RL6), Clinical Education LMS |
| Registered Nurse (RN) | `nurse` | Epic EMR, MAR, Patient Monitoring, PYXIS, Care Communication |
| Pharmacist (PharmD) | `pharmacist` | Pharmacy Management, PYXIS, Controlled Substance Monitor, Epic EMR, Drug Interaction DB |
| Radiology Technician | `radiology_tech` | PACS, RIS, Radiation Safety, Epic EMR, Modality Workstation |
| Medical Administrator | `medical_admin` | Epic (Registration/Billing), Insurance Portal, Scheduling, Revenue Cycle, Patient Registration (ADT) |
| IT / Security | `it_security` | Epic (Technical Admin), HIPAA Audit, Network Infrastructure, IAM, SIEM, Cloud Health Platform |

Gary understands both plain-language and formal titles — e.g. "cardiologist", "cardio doctor", "heart doctor" → `cardiologist`; "case manager", "clinical case manager" → `case_manager`; specialist titles ending in *-ologist* (oncologist, neurologist, …) map to `physician`. If no role is stated, it falls back to a general staff template rather than failing.

## Demo prompts

Paste any of these into **Ask Gary** (each onboarding prompt needs a **unique email**).

**Onboarding**

```text
Onboard Dr. Nina Prince as a cardiologist. Her email is nina.prince@cityhealth.org.
Add Dr. Leo Martin as a medical director. His email is leo.martin@cityhealth.org.
Onboard Priya Shah as a clinical case manager. Her email is priya.shah@cityhealth.org.
Add Maria Gomez as a clinical nurse manager. Her email is maria.g@cityhealth.org.
Create an account for Dr. John Doe, john.doe@cityhealth.org — he is a cardiologist.
```

**Offboarding**

```text
Offboard Dr. Marcus Reed immediately. Revoke all clinical system access and preserve patient records per HIPAA.
Terminate Grace Lee's access today and transfer her files to her supervisor.
```

**Terminating a single access**: open any clinician → each account row has a **Revoke** button.
**Terminating everything**: the **Offboard** button (or a Gary offboard prompt) revokes every account, session, and credential at once and produces an audit record.

## Running locally

**Backend** (Python 3.12+)

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows:  .venv\Scripts\activate   |  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Frontend** (Node 20+)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The API runs on <http://127.0.0.1:8000> (`/docs` for Swagger). The SQLite database is created and seeded with demo staff on first boot.

### Demo logins

| Role | Email | Password |
|------|-------|----------|
| System Admin (full access) | `admin@health.demo` | `admin123` |
| Department Head | `head@health.demo` | `dept123` |
| Staff Coordinator | `coordinator@health.demo` | `coord123` |
| Compliance Officer | `compliance@health.demo` | `comply123` |

Use **System Admin** for the full demo (onboarding, offboarding, and Gary). To restore a clean roster at any time, `POST /api/v1/demo/reset`.

## Tech stack

- **Backend:** FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic v2, SQLite, PyJWT, bcrypt, Resend (optional email)
- **Gary agent:** self-contained rule-based NLP (intent detection, role resolver, plan → execute → verify → report) with SSE streaming — no external LLM required
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, lucide-react

