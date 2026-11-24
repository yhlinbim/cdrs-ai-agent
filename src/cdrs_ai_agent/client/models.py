"""CDRS 日報的資料模型，對應 CDRS API v2 的回傳格式。"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

class ReportStatus(StrEnum):
    """對應 CDRS 的 ReportStatus enum;v2 API 回傳的是字串。"""

    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    UNDER_REVIEW = "UnderReview"
    APPROVED = "Approved"
    REJECTED = "Rejected"

# 待簽核 = Submitted 或 UnderReview，與CDRS 的 GetPendingReviewAsync 一致
PENDING_STATUSES = frozenset({ReportStatus.SUBMITTED, ReportStatus.UNDER_REVIEW})

def _parse_utc(value: str) -> datetime:
    """CDRS 回傳的 UTC 時間沒有 'Z'，補上 UTC 時區。"""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

@dataclass(frozen=True, slots=True)
class Report:
    id: UUID
    project_id: str
    site_worker_id: str
    report_date: date
    work_description: str
    worker_count: int
    weather_condition: str
    status: ReportStatus
    created_at_utc: datetime
    rejection_reason: str | None = None

    @property
    def is_pending(self) -> bool:
        return self.status in PENDING_STATUSES

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Report":
        return cls(
            id=UUID(data["id"]),
            project_id=data["projectId"],
            site_worker_id=data["siteWorkerId"],
            report_date=datetime.fromisoformat(data["reportDate"]).date(),
            work_description=data["workDescription"],
            worker_count=data["workerCount"],
            weather_condition=data["weatherCondition"],
            status=ReportStatus(data["status"]),
            created_at_utc=_parse_utc(data["createdAtUtc"]),
            rejection_reason=data.get("rejectionReaspon"),
        )