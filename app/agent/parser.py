import re
from datetime import date

from app.agent.schemas import (
    EmployeeHints,
    OffboardingActions,
    OffboardingPlan,
    OnboardingEmployeeData,
    OnboardingPlan,
    UnknownPlan,
)


# Lay-language and formal job titles → healthcare access templates.
# Every value here MUST be a key in app.services.ACCESS_TEMPLATES.
ROLE_TEMPLATES = {
    # Physicians
    "attending physician": {"department": "Clinical Medicine", "job_title": "Attending Physician", "access_template": "physician"},
    "physician": {"department": "Clinical Medicine", "job_title": "Physician", "access_template": "physician"},
    "doctor": {"department": "Clinical Medicine", "job_title": "Physician", "access_template": "physician"},
    "surgeon": {"department": "Surgery", "job_title": "Surgeon", "access_template": "physician"},
    "hospitalist": {"department": "Clinical Medicine", "job_title": "Hospitalist", "access_template": "physician"},
    "provider": {"department": "Clinical Medicine", "job_title": "Provider", "access_template": "physician"},
    "general practitioner": {"department": "Clinical Medicine", "job_title": "General Practitioner", "access_template": "physician"},
    "clinician": {"department": "Clinical Medicine", "job_title": "Clinician", "access_template": "physician"},
    # Cardiology
    "interventional cardiologist": {"department": "Cardiology", "job_title": "Interventional Cardiologist", "access_template": "cardiologist"},
    "cardiologist": {"department": "Cardiology", "job_title": "Cardiologist", "access_template": "cardiologist"},
    "cardiology": {"department": "Cardiology", "job_title": "Cardiologist", "access_template": "cardiologist"},
    # Leadership
    "chief medical officer": {"department": "Clinical Medicine", "job_title": "Chief Medical Officer", "access_template": "medical_director"},
    "medical director": {"department": "Clinical Medicine", "job_title": "Medical Director", "access_template": "medical_director"},
    "clinical director": {"department": "Clinical Medicine", "job_title": "Clinical Director", "access_template": "medical_director"},
    "director": {"department": "Clinical Medicine", "job_title": "Medical Director", "access_template": "medical_director"},
    # Case management
    "clinical case manager": {"department": "Case Management", "job_title": "Clinical Case Manager", "access_template": "case_manager"},
    "case manager": {"department": "Case Management", "job_title": "Case Manager", "access_template": "case_manager"},
    "utilization reviewer": {"department": "Case Management", "job_title": "Utilization Reviewer", "access_template": "case_manager"},
    # Nurse leadership
    "clinical nurse manager": {"department": "Clinical Nursing", "job_title": "Clinical Nurse Manager", "access_template": "clinical_nurse_manager"},
    "nurse manager": {"department": "Clinical Nursing", "job_title": "Nurse Manager", "access_template": "clinical_nurse_manager"},
    # Nurses
    "nurse practitioner": {"department": "Clinical Nursing", "job_title": "Nurse Practitioner", "access_template": "nurse"},
    "registered nurse": {"department": "Clinical Nursing", "job_title": "Registered Nurse", "access_template": "nurse"},
    "charge nurse": {"department": "Clinical Nursing", "job_title": "Charge Nurse", "access_template": "nurse"},
    "nurse": {"department": "Clinical Nursing", "job_title": "Registered Nurse", "access_template": "nurse"},
    # Pharmacy
    "pharmacist": {"department": "Pharmacy", "job_title": "Staff Pharmacist", "access_template": "pharmacist"},
    "pharmacy": {"department": "Pharmacy", "job_title": "Pharmacy Staff", "access_template": "pharmacist"},
    # Radiology
    "radiology technician": {"department": "Radiology", "job_title": "Radiology Technician", "access_template": "radiology_tech"},
    "radiology tech": {"department": "Radiology", "job_title": "Radiology Technician", "access_template": "radiology_tech"},
    "rad tech": {"department": "Radiology", "job_title": "Radiology Technician", "access_template": "radiology_tech"},
    "x-ray tech": {"department": "Radiology", "job_title": "X-Ray Technician", "access_template": "radiology_tech"},
    "imaging tech": {"department": "Radiology", "job_title": "Imaging Technician", "access_template": "radiology_tech"},
    "radiographer": {"department": "Radiology", "job_title": "Radiographer", "access_template": "radiology_tech"},
    # IT / Security
    "it security": {"department": "Information Technology", "job_title": "IT Security Analyst", "access_template": "it_security"},
    "security analyst": {"department": "Information Technology", "job_title": "Security Analyst", "access_template": "it_security"},
    "sysadmin": {"department": "Information Technology", "job_title": "Systems Administrator", "access_template": "it_security"},
    "software engineer": {"department": "Information Technology", "job_title": "Software Engineer", "access_template": "it_security"},
    "developer": {"department": "Information Technology", "job_title": "Software Developer", "access_template": "it_security"},
    "engineer": {"department": "Information Technology", "job_title": "Engineer", "access_template": "it_security"},
    "it": {"department": "Information Technology", "job_title": "IT Staff", "access_template": "it_security"},
    # Medical / administrative
    "medical administrator": {"department": "Administration", "job_title": "Medical Administrator", "access_template": "medical_admin"},
    "administrator": {"department": "Administration", "job_title": "Administrator", "access_template": "medical_admin"},
    "scheduler": {"department": "Administration", "job_title": "Scheduler", "access_template": "medical_admin"},
    "coordinator": {"department": "Administration", "job_title": "Staff Coordinator", "access_template": "medical_admin"},
    "receptionist": {"department": "Administration", "job_title": "Receptionist", "access_template": "medical_admin"},
    "billing": {"department": "Administration", "job_title": "Billing Specialist", "access_template": "medical_admin"},
    "coder": {"department": "Administration", "job_title": "Medical Coder", "access_template": "medical_admin"},
    "admin": {"department": "Administration", "job_title": "Administrator", "access_template": "medical_admin"},
}

# Default template when a role cannot be inferred — never blocks onboarding.
DEFAULT_ROLE = {"department": "Administration", "job_title": "Staff Member", "access_template": "medical_admin"}


ONBOARDING_TERMS = {
    "add",
    "hire",
    "new hire",
    "onboard",
    "create employee",
    "create account",
    "create an account",
    "set up account",
    "set up an account",
    "set up access",
    "make an account",
    "account for",
    "new employee",
    "joining",
    "joins",
    "starts",
    "starting",
    "grant access",
    "give access",
    "give him access",
    "give her access",
    "give them access",
    "needs access",
    "provision",
    "spin up",
    "register",
}

OFFBOARDING_TERMS = {
    "terminate",
    "offboard",
    "revoke",
    "deprovision",
    "deactivate",
    "suspend",
    "left",
    "leaving",
    "last day",
    "disable access",
    "remove access",
    "fire",
    "fired",
    "let go",
}


def normalize_instruction(instruction: str) -> str:
    return " ".join(instruction.strip().split())


def detect_intent(instruction: str) -> str:
    lowered = instruction.lower()

    onboarding_score = sum(
        1 for term in ONBOARDING_TERMS if term in lowered
    )
    offboarding_score = sum(
        1 for term in OFFBOARDING_TERMS if term in lowered
    )

    if onboarding_score > offboarding_score:
        return "onboard_employee"

    if offboarding_score > onboarding_score:
        return "offboard_employee"

    return "unknown"


def extract_email(instruction: str) -> str | None:
    match = re.search(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        instruction,
    )
    return match.group(0) if match else None


def extract_name(instruction: str) -> str | None:
    patterns = [
        (
            r"(?:add|hire|onboard|terminate|offboard|remove|disable|register)\s+"
            r"(?:dr\.?\s+|mr\.?\s+|ms\.?\s+|mrs\.?\s+|nurse\s+)?"
            r"([A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){1,2}?)"
            r"(?=\s+(?:as|immediately|today|tomorrow|from|who|and|is|was)|[.,]|$)"
        ),
        (
            r"(?:account for|access for|set up|provision|onboard)\s+"
            r"(?:dr\.?\s+|mr\.?\s+|ms\.?\s+|mrs\.?\s+|nurse\s+)?"
            r"([A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){1,2}?)"
            r"(?=\s+(?:as|a\s|an\s|the\s|who|and|is|with|,|\.)|[.,]|$)"
        ),
        (
            r"(?:named|called)\s+"
            r"(?:dr\.?\s+|mr\.?\s+|ms\.?\s+|mrs\.?\s+|nurse\s+)?"
            r"([A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){1,2}?)"
            r"(?=\s+(?:as|a\s|an\s|who|and|is|with|,|\.)|[.,]|$)"
        ),
        (
            r"([A-Za-z][A-Za-z'-]+(?:\s+[A-Za-z][A-Za-z'-]+){1,2})\s+"
            r"(?:left|is leaving|was fired|starts|is joining|joined)"
        ),
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            instruction,
            flags=re.IGNORECASE,
        )

        if match:
            return " ".join(
                part.capitalize()
                for part in match.group(1).strip().split()
            )

    return None


def extract_manager(instruction: str) -> str | None:
    patterns = [
        r"(?:manager is|manager:|reports to)\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
        r"(?:(?:transfer|move) .*? to)\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            instruction,
            flags=re.IGNORECASE,
        )

        if match:
            return " ".join(
                part.capitalize()
                for part in match.group(1).strip().split()
            )

    return None


def detect_role(instruction: str) -> dict | None:
    lowered = instruction.lower()

    # Longest match first so "registered nurse" beats "nurse", etc.
    # Whole-word match so short keys like "it" don't match inside "cityhealth".
    for role_name in sorted(
        ROLE_TEMPLATES,
        key=len,
        reverse=True,
    ):
        if re.search(rf"\b{re.escape(role_name)}\b", lowered):
            return ROLE_TEMPLATES[role_name]

    # Heuristic fallback: medical specialties ("cardiologist", "oncologist",
    # "neurologist", …) and generic surgeon titles map to the physician template.
    if re.search(r"\b\w+ologist\b", lowered) or "surgeon" in lowered:
        return {
            "department": "Clinical Medicine",
            "job_title": "Physician",
            "access_template": "physician",
        }

    return None


def parse_onboarding(instruction: str) -> OnboardingPlan:
    full_name = extract_name(instruction)
    company_email = extract_email(instruction)
    manager_name = extract_manager(instruction)
    role = detect_role(instruction)

    # Role is optional — if it can't be inferred we fall back to a general
    # staff template rather than blocking the request.
    effective_role = role or DEFAULT_ROLE

    missing_fields = []

    if not full_name:
        missing_fields.append("full_name")

    if not company_email:
        missing_fields.append("company_email")

    confidence = 0.95

    if missing_fields:
        confidence = max(
            0.35,
            confidence - (0.2 * len(missing_fields)),
        )
    elif role is None:
        # Proceeded with a default role — reflect the slight uncertainty.
        confidence = 0.8

    employee = OnboardingEmployeeData(
        full_name=full_name or "Unknown Employee",
        company_email=company_email or "unknown@invalid.local",
        department=effective_role["department"],
        job_title=effective_role["job_title"],
        manager_name=manager_name,
        start_date=date.today(),
        access_template=effective_role["access_template"],
    )

    return OnboardingPlan(
        employee=employee,
        confidence=confidence,
        missing_fields=missing_fields,
    )


def parse_offboarding(instruction: str) -> OffboardingPlan:
    lowered = instruction.lower()

    full_name = extract_name(instruction)
    company_email = extract_email(instruction)
    manager_name = extract_manager(instruction)

    preserve_mailbox = not any(
        phrase in lowered
        for phrase in {
            "delete mailbox",
            "remove mailbox",
            "do not preserve mailbox",
        }
    )

    transfer_files = any(
        phrase in lowered
        for phrase in {
            "transfer files",
            "transfer her files",
            "transfer his files",
            "transfer their files",
            "transfer documents",
            "transfer her documents",
            "transfer his documents",
            "transfer their documents",
            "transfer assets",
            "transfer her assets",
            "transfer his assets",
            "transfer their assets",
            "move files",
            "move her files",
            "move his files",
            "move their files",
            "move documents",
            "move her documents",
            "move his documents",
            "move their documents",
        }
    )

    freeze_card = not any(
        phrase in lowered
        for phrase in {
            "do not freeze card",
            "leave card active",
        }
    )

    revoke_all = not any(
        phrase in lowered
        for phrase in {
            "keep access",
            "leave all access active",
        }
    )

    exceptions = []

    keep_match = re.search(
        r"(?:keep|leave)\s+([A-Za-z0-9 ._-]+?)\s+"
        r"(?:active|enabled|for)",
        instruction,
        re.IGNORECASE,
    )

    if keep_match:
        exceptions.append(keep_match.group(1).strip())

    confidence = 0.95

    if not full_name and not company_email:
        confidence = 0.55

    return OffboardingPlan(
        employee_hints=EmployeeHints(
            full_name=full_name,
            company_email=company_email,
            manager_name=manager_name,
        ),
        actions=OffboardingActions(
            revoke_all_access=revoke_all,
            preserve_mailbox=preserve_mailbox,
            transfer_files_to_manager=transfer_files,
            transfer_to=manager_name,
            freeze_company_card=freeze_card,
            preserve_audit_logs=True,
            revoke_sessions=True,
            revoke_credentials=True,
        ),
        exceptions=exceptions,
        confidence=confidence,
    )


def parse_instruction(
    instruction: str,
) -> OnboardingPlan | OffboardingPlan | UnknownPlan:
    cleaned = normalize_instruction(instruction)
    intent = detect_intent(cleaned)

    if intent == "onboard_employee":
        return parse_onboarding(cleaned)

    if intent == "offboard_employee":
        return parse_offboarding(cleaned)

    return UnknownPlan(
        reason=(
            "The instruction did not clearly describe employee "
            "onboarding or offboarding."
        ),
        confidence=0.2,
    )
