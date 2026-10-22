from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./gatekeep_health.db"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # JWT — override in production: python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret_key: str = "change-me-in-production-generate-with-secrets-token-hex-32"
    access_token_expire_hours: int = 8

    # Email via Resend (optional — if blank, emails are only logged to console)
    resend_api_key: str = ""
    email_from: str = "GateKeep Health <no-reply@gatekeephealth.com>"
    app_url: str = "http://localhost:3000"

    # Demo credentials — used to seed the DB on first boot and demo reset
    demo_admin_email: str = "admin@health.demo"
    demo_admin_password: str = "admin123"
    demo_head_email: str = "head@health.demo"
    demo_head_password: str = "dept123"
    demo_coordinator_email: str = "coordinator@health.demo"
    demo_coordinator_password: str = "coord123"
    demo_compliance_email: str = "compliance@health.demo"
    demo_compliance_password: str = "comply123"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
