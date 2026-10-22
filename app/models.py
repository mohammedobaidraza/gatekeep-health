from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String, index=True)
    company_email: Mapped[str] = mapped_column(String, unique=True, index=True)
    personal_email: Mapped[str | None] = mapped_column(String, nullable=True)
    department: Mapped[str] = mapped_column(String)
    job_title: Mapped[str] = mapped_column(String)
    manager_name: Mapped[str | None] = mapped_column(String, nullable=True)
    employment_status: Mapped[str] = mapped_column(String, default="active")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=30)
    last_access_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Healthcare-specific fields
    npi_number: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    license_number: Mapped[str | None] = mapped_column(String, nullable=True)
    license_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    license_type: Mapped[str | None] = mapped_column(String, nullable=True)  # MD, DO, RN, LPN, PharmD, RT, NP
    dea_number: Mapped[str | None] = mapped_column(String, nullable=True)
    privilege_level: Mapped[str] = mapped_column(String, default="standard")  # full, limited, supervised, standard
    credential_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)

    accounts = relationship("EmployeeAccount", back_populates="employee", cascade="all, delete-orphan")
    assets = relationship("CompanyAsset", back_populates="employee", cascade="all, delete-orphan")


class EmployeeAccount(Base):
    __tablename__ = "employee_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    platform: Mapped[str] = mapped_column(String)
    account_type: Mapped[str] = mapped_column(String, default="clinical_system")
    identifier: Mapped[str] = mapped_column(String)
    access_level: Mapped[str] = mapped_column(String, default="standard")
    status: Mapped[str] = mapped_column(String, default="active")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_level: Mapped[str] = mapped_column(String, default="low")
    external_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    revocation_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    employee = relationship("Employee", back_populates="accounts")
    sessions = relationship("AccountSession", back_populates="account", cascade="all, delete-orphan")
    credentials = relationship("Credential", back_populates="account", cascade="all, delete-orphan")


class CompanyAsset(Base):
    __tablename__ = "company_assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    asset_type: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    identifier: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True)
    employee = relationship("Employee", back_populates="assets")


class AccountSession(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_account_id: Mapped[int] = mapped_column(ForeignKey("employee_accounts.id"), index=True)
    session_type: Mapped[str] = mapped_column(String, default="workstation")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account = relationship("EmployeeAccount", back_populates="sessions")


class Credential(Base):
    __tablename__ = "credentials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_account_id: Mapped[int] = mapped_column(ForeignKey("employee_accounts.id"), index=True)
    credential_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    account = relationship("EmployeeAccount", back_populates="credentials")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    result: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TerminationRun(Base):
    __tablename__ = "termination_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    actor: Mapped[str] = mapped_column(String)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="completed")
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    """GateKeep system users — the people who log in, not the clinicians they manage."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="staff_coordinator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
