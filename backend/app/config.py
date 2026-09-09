from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://pstreview:change-me@localhost:5432/pstreview"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = DEFAULT_JWT_SECRET
    cookie_secure: bool = False
    storage_root: str = "/data"
    backend_cors_origins: str = "http://localhost"
    enable_api_docs: bool = False
    # How many documents a single import job renders in parallel (each gets
    # its own thread + DB session -- see app.tasks.render_tasks). Independent
    # of the Celery worker's own --concurrency, which controls how many
    # import/export jobs run at once.
    render_concurrency: int = 4
    # How many manifest entries (emails, contacts, calendar items) a single
    # import job parses/stages in parallel -- see app.tasks.ingest_tasks.
    # Lighter per-item work than rendering, so a higher default is fine.
    parse_concurrency: int = 8
    # Fernet key encrypting the OIDC client secret at rest (see app/services/encryption.py).
    # Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    secret_encryption_key: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
