"""Email delivery via Resend. Falls back to console logging if no API key is set."""
import logging
from datetime import date

from app.config import settings

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key:
        logger.info("[EMAIL] To: %s | Subject: %s", to, subject)
        return False
    try:
        import resend
        resend.api_key = settings.resend_api_key
        resend.Emails.send({"from": settings.email_from, "to": to, "subject": subject, "html": html})
        return True
    except Exception as exc:
        logger.error("Resend failed: %s", exc)
        return False


def send_welcome(to_email: str, name: str, role: str, temp_password: str) -> bool:
    role_label = role.replace("_", " ").title()
    html = f"""
    <h2>Welcome to GateKeep Health</h2>
    <p>Hi {name}, your account has been created.</p>
    <ul>
      <li><strong>Role:</strong> {role_label}</li>
      <li><strong>Login:</strong> {to_email}</li>
      <li><strong>Temporary password:</strong> <code>{temp_password}</code></li>
    </ul>
    <p>Please change your password after your first sign-in.</p>
    <p><a href="{settings.app_url}/login">Sign in to GateKeep Health</a></p>
    """
    return _send(to_email, "Welcome to GateKeep Health", html)


def send_credential_expiry_alert(
    to_email: str,
    clinician_name: str,
    department: str,
    license_type: str,
    days_remaining: int,
    expiry_date: date,
) -> bool:
    urgency = "URGENT: " if days_remaining <= 7 else ("Warning: " if days_remaining <= 30 else "")
    html = f"""
    <h2>Credential Expiry Alert</h2>
    <table>
      <tr><td><strong>Clinician</strong></td><td>{clinician_name}</td></tr>
      <tr><td><strong>Department</strong></td><td>{department}</td></tr>
      <tr><td><strong>License type</strong></td><td>{license_type}</td></tr>
      <tr><td><strong>Expiry date</strong></td><td>{expiry_date}</td></tr>
      <tr><td><strong>Days remaining</strong></td><td>{days_remaining}</td></tr>
    </table>
    <p><a href="{settings.app_url}/dashboard">Open GateKeep Health</a></p>
    """
    return _send(
        to_email,
        f"{urgency}Credential expiry — {clinician_name} ({days_remaining}d)",
        html,
    )


def send_offboard_confirmation(
    to_email: str,
    clinician_name: str,
    actor: str,
    revoked_systems: list[str],
) -> bool:
    systems_html = "".join(f"<li>{s}</li>" for s in revoked_systems)
    html = f"""
    <h2>Offboarding Confirmed</h2>
    <p><strong>{clinician_name}</strong> has been offboarded.</p>
    <ul>
      <li><strong>Completed by:</strong> {actor}</li>
      <li><strong>Systems revoked ({len(revoked_systems)}):</strong>
        <ul>{systems_html}</ul>
      </li>
    </ul>
    <p>Patient records have been preserved per HIPAA requirements.</p>
    <p><a href="{settings.app_url}/dashboard">Open GateKeep Health</a></p>
    """
    return _send(to_email, f"Offboarding complete — {clinician_name}", html)
