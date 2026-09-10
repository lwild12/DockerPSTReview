from datetime import datetime

from pydantic import BaseModel


class AiReviewSummary(BaseModel):
    criteria: str
    ollama_configured: bool
    last_run_started_at: datetime | None
    last_run_completed_at: datetime | None
    candidate_count: int
    unscored_count: int
    queued_count: int
    running_count: int
    completed_count: int
    failed_count: int


class AiReviewCriteriaUpdate(BaseModel):
    criteria: str


class AiReviewRunRequest(BaseModel):
    # Default: only score candidates that have never been scored, previously
    # failed, or were scored against a since-changed criteria string. True
    # rescores every candidate regardless of its current status.
    rescore_all: bool = False
