import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CaseAnalyticsSummary(BaseModel):
    computed_at: datetime | None
    near_duplicate_cluster_count: int
    non_inclusive_email_count: int


class NearDuplicateClusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_count: int
