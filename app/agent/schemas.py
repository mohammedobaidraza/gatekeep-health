from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


AgentIntent = Literal[
    "onboard_employee",
    "offboard_employee",
    "unknown",
]


class AgentRunRequest(BaseModel):
    instruction: str = Field(min_length=5, max_length=5000)
    auto_execute: bool = True


class EmployeeHints(BaseModel):
    full_name: str | None = None
    company_email: EmailStr | None = None
    personal_email: EmailStr | None = None
    department: str | None = None
    job_title: str | None = None
    manager_name: str | None = None


class OnboardingEmployeeData(BaseModel):
    full_name: str
    company_email: EmailStr
    personal_email: EmailStr | None = None
    department: str
    job_title: str
    manager_name: str | None = None
    start_date: date | None = None
    access_template: Literal[
        "physician",
        "nurse",
        "pharmacist",
        "radiology_tech",
        "medical_admin",
        "it_security",
    ]


class OnboardingPlan(BaseModel):
    intent: Literal["onboard_employee"] = "onboard_employee"
    employee: OnboardingEmployeeData
    confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = []


class OffboardingActions(BaseModel):
    revoke_all_access: bool = True
    preserve_records: bool = True          # HIPAA record retention
    transfer_files_to_manager: bool = True
    transfer_to: str | None = None
    freeze_company_card: bool = True
    preserve_audit_logs: bool = True
    revoke_sessions: bool = True
    revoke_credentials: bool = True
    notify_medical_staff_office: bool = True
    revoke_prescribing_access: bool = True

    # Back-compat alias so orchestrator works without changes
    @property
    def preserve_mailbox(self) -> bool:
        return self.preserve_records


class OffboardingPlan(BaseModel):
    intent: Literal["offboard_employee"] = "offboard_employee"
    employee_hints: EmployeeHints
    effective_at: datetime | None = None
    actions: OffboardingActions = OffboardingActions()
    exceptions: list[str] = []
    confidence: float = Field(ge=0, le=1)


class UnknownPlan(BaseModel):
    intent: Literal["unknown"] = "unknown"
    reason: str
    confidence: float = Field(default=0, ge=0, le=1)


class AgentStepResult(BaseModel):
    sequence: int
    stage: Literal["parse", "resolve", "plan", "execute", "verify", "report"]
    status: Literal["pending", "running", "completed", "verified", "failed", "needs_input"]
    message: str
    evidence: dict = {}


class AgentRunResponse(BaseModel):
    run_id: str
    intent: AgentIntent
    status: Literal["planned", "completed", "failed", "needs_input"]
    employee_id: int | None = None
    employee_name: str | None = None
    confidence: float
    steps: list[AgentStepResult]
    summary: dict = {}
    message: str
