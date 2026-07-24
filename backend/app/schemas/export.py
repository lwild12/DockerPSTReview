import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.export import ExportStatus, ExportType


class ExportJobCreate(BaseModel):
    review_set_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] | None = None
    export_type: ExportType
    apply_bates: bool = False
    bates_prefix: str = ""
    bates_start_number: int = 1
    bates_digit_padding: int = 6

    @model_validator(mode="after")
    def _require_a_source(self):
        if not self.review_set_id and not self.document_ids:
            raise ValueError("Provide either review_set_id or document_ids")
        return self


class ExportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    review_set_id: uuid.UUID | None
    production_number: int
    export_type: ExportType
    apply_bates: bool
    bates_prefix: str
    bates_start_number: int
    bates_digit_padding: int
    bates_end_number: int | None
    document_ids: list[uuid.UUID]
    status: ExportStatus
    output_storage_path: str
    requested_by_id: uuid.UUID
    created_at: datetime
    completed_at: datetime | None
    error_message: str
