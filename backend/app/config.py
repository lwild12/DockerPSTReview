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
