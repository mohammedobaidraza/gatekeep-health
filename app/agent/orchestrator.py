from contextvars import ContextVar
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.parser import parse_instruction
from app.agent.resolver import resolve_employee
from app.agent.schemas import (
    AgentRunResponse,
    AgentStepResult,
    OffboardingPlan,
    OnboardingPlan,
    UnknownPlan,
)
from app.models import Employee, EmployeeAccount

# Set this context var before running run_agent in a thread to receive
# each step as it is emitted (used by the SSE streaming endpoint).
step_emitter: ContextVar[Callable[[AgentStepResult], None] | None] = ContextVar(
    "step_emitter", default=None
)
from app.schemas import TerminationRequest
from app.services import (
    add_account,
    audit,
    auto_provision,
    employee_detail,
    group_access,
    terminate,
)


def _healthcare_risk(department: str) -> int:
    dept = (department or "").lower()
    if any(kw in dept for kw in ["medicine", "surgery", "icu", "emergency"]):
        return 75
    if any(kw in dept for kw in ["pharmacy", "nursing"]):
        return 65
    if any(kw in dept for kw in ["radiology", "imaging"]):
        return 55
    if "information technology" in dept or "it" in dept or "security" in dept:
        return 45
    return 35


def make_step(
    sequence: int,
    stage: str,
    status: str,
    message: str,
    evidence: dict | None = None,
) -> AgentStepResult:
    step = AgentStepResult(
        sequence=sequence,
        stage=stage,
        status=status,
        message=message,
        evidence=evidence or {},
    )
    emitter = step_emitter.get()
    if emitter is not None:
        try:
            emitter(step)
        except Exception:
            pass
    return step


def build_onboarding_plan(
    db: Session,
    plan: OnboardingPlan,
) -> AgentRunResponse:
    steps: list[AgentStepResult] = []

    steps.append(
        make_step(
            1,
            "parse",
            "completed",
            "Detected employee onboarding request.",
            {
                "intent": plan.intent,
                "confidence": plan.confidence,
            },
        )
    )

    if plan.missing_fields:
        steps.append(
            make_step(
                2,
                "plan",
                "needs_input",
                "Required onboarding information is missing.",
                {
                    "missing_fields": plan.missing_fields,
                },
            )
        )

        return AgentRunResponse(
            run_id=str(uuid4()),
            intent=plan.intent,
            status="needs_input",
            confidence=plan.confidence,
            steps=steps,
            summary={
                "missing_fields": plan.missing_fields,
            },
            message=(
                "The onboarding request needs more information "
                "before it can be executed."
            ),
        )

    existing_employee = db.scalar(
        select(Employee).where(
            Employee.company_email
            == str(plan.employee.company_email)
        )
    )

    if existing_employee:
        steps.append(
            make_step(
                2,
                "resolve",
                "failed",
                "An employee with this company email already exists.",
                {
                    "employee_id": existing_employee.id,
                    "employee_name": existing_employee.full_name,
                    "company_email": existing_employee.company_email,
                },
            )
        )

        return AgentRunResponse(
            run_id=str(uuid4()),
            intent=plan.intent,
            status="failed",
            employee_id=existing_employee.id,
            employee_name=existing_employee.full_name,
            confidence=plan.confidence,
            steps=steps,
            summary={
                "duplicate_company_email": True,
            },
            message="Employee onboarding was not executed.",
        )

    steps.append(
        make_step(
            2,
            "resolve",
            "completed",
            "No existing employee uses this company email.",
            {
                "company_email": str(
                    plan.employee.company_email
                ),
            },
        )
    )

    steps.append(
        make_step(
            3,
            "plan",
            "completed",
            "Onboarding plan is ready.",
            {
                "employee": plan.employee.model_dump(
                    mode="json"
                ),
                "access_template": (
                    plan.employee.access_template
                ),
            },
        )
    )

    return AgentRunResponse(
        run_id=str(uuid4()),
        intent=plan.intent,
        status="planned",
        employee_name=plan.employee.full_name,
        confidence=plan.confidence,
        steps=steps,
        summary={
            "employee_will_be_created": True,
            "access_template": (
                plan.employee.access_template
            ),
            "execution_enabled": False,
        },
        message=(
            "Onboarding plan created successfully. "
            "Execution is not connected yet."
        ),
    )


def build_offboarding_plan(
    db: Session,
    plan: OffboardingPlan,
) -> AgentRunResponse:
    steps: list[AgentStepResult] = []

    steps.append(
        make_step(
            1,
            "parse",
            "completed",
            "Detected employee offboarding request.",
            {
                "intent": plan.intent,
                "confidence": plan.confidence,
                "actions": plan.actions.model_dump(),
                "exceptions": plan.exceptions,
            },
        )
    )

    resolution = resolve_employee(
        db,
        plan.employee_hints,
    )

    if resolution.status == "not_found":
        steps.append(
            make_step(
                2,
                "resolve",
                "failed",
                resolution.message,
                {
                    "candidates": [],
                },
            )
        )

        return AgentRunResponse(
            run_id=str(uuid4()),
            intent=plan.intent,
            status="failed",
            confidence=plan.confidence,
            steps=steps,
            summary={
                "employee_resolved": False,
            },
            message=(
                "Offboarding could not continue because "
                "the employee was not found."
            ),
        )

    if resolution.status == "ambiguous":
        steps.append(
            make_step(
                2,
                "resolve",
                "needs_input",
                resolution.message,
                {
                    "candidates": [
                        candidate.model_dump()
                        for candidate in resolution.candidates
                    ],
                },
            )
        )

        return AgentRunResponse(
            run_id=str(uuid4()),
            intent=plan.intent,
            status="needs_input",
            confidence=resolution.confidence,
            steps=steps,
            summary={
                "employee_resolved": False,
                "candidate_count": len(
                    resolution.candidates
                ),
            },
            message=(
                "Multiple employees may match. "
                "Manual selection is required."
            ),
        )

    employee = db.get(
        Employee,
        resolution.employee_id,
    )

    if not employee:
        steps.append(
            make_step(
                2,
                "resolve",
                "failed",
                "Resolved employee record no longer exists.",
            )
        )

        return AgentRunResponse(
            run_id=str(uuid4()),
            intent=plan.intent,
            status="failed",
            confidence=resolution.confidence,
            steps=steps,
            summary={},
            message="Offboarding could not continue.",
        )

    steps.append(
        make_step(
            2,
            "resolve",
            "completed",
            resolution.message,
            {
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "company_email": employee.company_email,
                "employment_status": (
                    employee.employment_status
                ),
                "match_reason": (
                    resolution.match_reason
                ),
            },
        )
    )

    accounts = list(
        db.scalars(
            select(EmployeeAccount)
            .where(
                EmployeeAccount.employee_id
                == employee.id
            )
            .order_by(EmployeeAccount.platform)
        ).all()
    )

    active_accounts = [
        account
        for account in accounts
        if account.status == "active"
    ]

    steps.append(
        make_step(
            3,
            "plan",
            "completed",
            "Offboarding plan is ready.",
            {
                "employee_status": (
                    employee.employment_status
                ),
                "accounts_discovered": len(accounts),
                "active_accounts": len(active_accounts),
                "platforms": [
                    {
                        "id": account.id,
                        "platform": account.platform,
                        "identifier": account.identifier,
                        "status": account.status,
                    }
                    for account in accounts
                ],
                "requested_actions": (
                    plan.actions.model_dump()
                ),
                "exceptions": plan.exceptions,
            },
        )
    )

    return AgentRunResponse(
        run_id=str(uuid4()),
        intent=plan.intent,
        status="planned",
        employee_id=employee.id,
        employee_name=employee.full_name,
        confidence=min(
            plan.confidence,
            resolution.confidence,
        ),
        steps=steps,
        summary={
            "employee_resolved": True,
            "accounts_discovered": len(accounts),
            "active_accounts": len(active_accounts),
            "execution_enabled": False,
        },
        message=(
            "Offboarding plan created successfully. "
            "No access was revoked during this test."
        ),
    )



def execute_onboarding(
    db: Session,
    plan: OnboardingPlan,
    actor: str,
) -> AgentRunResponse:
    planned = build_onboarding_plan(db, plan)

    if planned.status != "planned":
        return planned

    employee = Employee(
        full_name=plan.employee.full_name,
        company_email=str(plan.employee.company_email),
        personal_email=(
            str(plan.employee.personal_email)
            if plan.employee.personal_email
            else None
        ),
        department=plan.employee.department,
        job_title=plan.employee.job_title,
        manager_name=plan.employee.manager_name,
        start_date=plan.employee.start_date,
        employment_status="active",
        risk_score=_healthcare_risk(plan.employee.department),
    )

    db.add(employee)
    db.commit()
    db.refresh(employee)

    add_account(
        db,
        employee,
        "Staff Directory",
        employee.company_email,
        "Employee",
        "low",
        "directory",
        sessions=0,
    )

    created_accounts = auto_provision(
        db,
        employee,
        template_key=plan.employee.access_template,
    )

    all_accounts = list(
        db.scalars(
            select(EmployeeAccount)
            .where(EmployeeAccount.employee_id == employee.id)
            .order_by(EmployeeAccount.platform)
        ).all()
    )

    active_accounts = [
        account
        for account in all_accounts
        if account.status == "active"
    ]

    expected_count = len(created_accounts) + 1

    verified = (
        len(all_accounts) == expected_count
        and len(active_accounts) == expected_count
    )

    audit(
        db,
        employee.id,
        actor,
        "agent_onboard_employee",
        employee.company_email,
        "verified" if verified else "failed",
        (
            f"template={plan.employee.access_template}; "
            f"expected_accounts={expected_count}; "
            f"actual_accounts={len(all_accounts)}"
        ),
    )

    steps = list(planned.steps)

    steps.append(
        make_step(
            4,
            "execute",
            "completed",
            "Employee created and access provisioned.",
            {
                "employee_id": employee.id,
                "accounts_created": len(all_accounts),
                "platforms": [
                    account.platform
                    for account in all_accounts
                ],
            },
        )
    )

    steps.append(
        make_step(
            5,
            "verify",
            "verified" if verified else "failed",
            (
                "All expected accounts were created and verified."
                if verified
                else "Provisioning verification failed."
            ),
            {
                "expected_accounts": expected_count,
                "actual_accounts": len(all_accounts),
                "active_accounts": len(active_accounts),
            },
        )
    )

    return AgentRunResponse(
        run_id=planned.run_id,
        intent="onboard_employee",
        status="completed" if verified else "failed",
        employee_id=employee.id,
        employee_name=employee.full_name,
        confidence=plan.confidence,
        steps=steps,
        summary={
            "employee_created": True,
            "access_template": plan.employee.access_template,
            "accounts_created": len(all_accounts),
            "accounts_verified": len(active_accounts),
            "verification_passed": verified,
        },
        access_groups=group_access(all_accounts),
        access_action="granted",
        message=(
            "Employee onboarding completed and verified."
            if verified
            else "Employee was created, but verification failed."
        ),
    )


def execute_offboarding(
    db: Session,
    plan: OffboardingPlan,
    actor: str,
) -> AgentRunResponse:
    planned = build_offboarding_plan(db, plan)

    if planned.status != "planned":
        return planned

    employee = db.get(Employee, planned.employee_id)

    if not employee:
        return AgentRunResponse(
            run_id=planned.run_id,
            intent="offboard_employee",
            status="failed",
            confidence=planned.confidence,
            steps=planned.steps,
            summary={},
            message="Resolved employee no longer exists.",
        )

    request = TerminationRequest(
        effective_at=plan.effective_at,
        preserve_mailbox=plan.actions.preserve_mailbox,
        transfer_files_to_manager=(
            plan.actions.transfer_files_to_manager
        ),
        freeze_company_card=plan.actions.freeze_company_card,
    )

    termination_result = terminate(
        db,
        employee,
        actor,
        request,
    )

    db.refresh(employee)

    all_accounts = list(
        db.scalars(
            select(EmployeeAccount).where(
                EmployeeAccount.employee_id == employee.id
            )
        ).all()
    )

    active_accounts = [
        account
        for account in all_accounts
        if account.status == "active"
    ]

    active_sessions = sum(
        1
        for account in all_accounts
        for session in account.sessions
        if session.active
    )

    active_credentials = sum(
        1
        for account in all_accounts
        for credential in account.credentials
        if credential.status == "active"
    )

    unverified_accounts = [
        account
        for account in all_accounts
        if account.status != "active"
        and not account.revocation_verified
    ]

    verified = (
        employee.employment_status == "terminated"
        and len(active_accounts) == 0
        and active_sessions == 0
        and active_credentials == 0
        and len(unverified_accounts) == 0
    )

    steps = list(planned.steps)

    steps.append(
        make_step(
            4,
            "execute",
            "completed",
            "Employee termination workflow executed.",
            {
                "termination_result": termination_result,
            },
        )
    )

    steps.append(
        make_step(
            5,
            "verify",
            "verified" if verified else "failed",
            (
                "All access paths were revoked and verified."
                if verified
                else "One or more access paths remain unresolved."
            ),
            {
                "employment_status": employee.employment_status,
                "active_accounts": len(active_accounts),
                "active_sessions": active_sessions,
                "active_credentials": active_credentials,
                "unverified_accounts": [
                    {
                        "id": account.id,
                        "platform": account.platform,
                        "status": account.status,
                    }
                    for account in unverified_accounts
                ],
            },
        )
    )

    summary = dict(termination_result.get("summary", {}))

    summary.update(
        {
            "active_accounts_remaining": len(active_accounts),
            "active_sessions_remaining": active_sessions,
            "active_credentials_remaining": active_credentials,
            "verification_passed": verified,
        }
    )

    return AgentRunResponse(
        run_id=planned.run_id,
        intent="offboard_employee",
        status="completed" if verified else "failed",
        employee_id=employee.id,
        employee_name=employee.full_name,
        confidence=planned.confidence,
        steps=steps,
        summary=summary,
        access_groups=group_access(all_accounts),
        access_action="revoked",
        message=(
            "Employee offboarding completed and verified."
            if verified
            else "Offboarding executed, but verification failed."
        ),
    )

def run_agent(
    db: Session,
    instruction: str,
    auto_execute: bool = False,
    actor: str = "gatekeep-agent",
) -> AgentRunResponse:
    plan = parse_instruction(instruction)

    if isinstance(plan, OnboardingPlan):
        if auto_execute:
            return execute_onboarding(
                db,
                plan,
                actor,
            )

        return build_onboarding_plan(
            db,
            plan,
        )

    if isinstance(plan, OffboardingPlan):
        if auto_execute:
            return execute_offboarding(
                db,
                plan,
                actor,
            )

        return build_offboarding_plan(
            db,
            plan,
        )

    if isinstance(plan, UnknownPlan):
        return AgentRunResponse(
            run_id=str(uuid4()),
            intent="unknown",
            status="needs_input",
            confidence=plan.confidence,
            steps=[
                make_step(
                    1,
                    "parse",
                    "needs_input",
                    plan.reason,
                )
            ],
            summary={},
            message=(
                "The agent could not determine whether "
                "this is onboarding or offboarding."
            ),
        )

    raise RuntimeError("Unsupported agent plan type")

