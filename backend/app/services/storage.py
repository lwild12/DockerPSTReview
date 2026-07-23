import uuid
from pathlib import Path

from app.config import get_settings

settings = get_settings()


def case_root(case_id: uuid.UUID) -> Path:
    return Path(settings.storage_root) / "cases" / str(case_id)


def uploads_dir(case_id: uuid.UUID) -> Path:
    return case_root(case_id) / "uploads"


def staging_dir(case_id: uuid.UUID, import_job_id: uuid.UUID) -> Path:
    return case_root(case_id) / "staging" / str(import_job_id)


def native_dir(case_id: uuid.UUID) -> Path:
    return case_root(case_id) / "native"


def rendered_dir(case_id: uuid.UUID) -> Path:
    return case_root(case_id) / "rendered"


def exports_dir(case_id: uuid.UUID) -> Path:
    return case_root(case_id) / "exports"


def save_upload(case_id: uuid.UUID, import_job_id: uuid.UUID, filename: str, content: bytes) -> str:
    directory = uploads_dir(case_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{import_job_id}_{filename}"
    path.write_bytes(content)
    return str(path)


def save_native_file(
    case_id: uuid.UUID, document_id: uuid.UUID, filename: str, content: bytes
) -> str:
    directory = native_dir(case_id) / str(document_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (filename or "attachment")
    path.write_bytes(content)
    return str(path)
