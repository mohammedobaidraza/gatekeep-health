from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./gatekeep_health.db"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # System Admin — full access
    demo_admin_email: str = "admin@health.demo"
    demo_admin_password: str = "admin123"
    demo_admin_token: str = "ghk-admin-2026"

    # Department Head — view + create, cannot terminate or revoke
    demo_head_email: str = "head@health.demo"
    demo_head_password: str = "dept123"
    demo_head_token: str = "ghk-head-2026"

    # Staff Coordinator — view + create only
    demo_coordinator_email: str = "coordinator@health.demo"
    demo_coordinator_password: str = "coord123"
    demo_coordinator_token: str = "ghk-coord-2026"

    # Compliance Officer — view + audit + freeze/revoke access
    demo_compliance_email: str = "compliance@health.demo"
    demo_compliance_password: str = "comply123"
    demo_compliance_token: str = "ghk-comply-2026"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
