import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.importjob import ImportStatus


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    custodian_id: uuid.UUID
    uploaded_filename: str
    status: ImportStatus
    error_message: str
    stats: dict
    created_by_id: uuid.UUID
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
