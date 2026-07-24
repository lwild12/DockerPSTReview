from cryptography.fernet import Fernet

from app.config import get_settings


class EncryptionNotConfigured(Exception):
    pass


def _get_fernet() -> Fernet:
    key = get_settings().secret_encryption_key
    if not key:
        raise EncryptionNotConfigured(
            "SECRET_ENCRYPTION_KEY is not set — required to store the OIDC client secret. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()
