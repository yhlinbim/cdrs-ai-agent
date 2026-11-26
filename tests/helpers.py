"""測試共用的資料工廠與假物件。"""

from uuid import uuid4

from cdrs_ai_agent.client.models import Report


def make_report(**overrides: object) -> Report:
    """建立測試用的 Report；只要寫出這個測試在意的欄位，其他用預設值。"""
    data: dict[str, object] = {
        "id": str(uuid4()),
        "projectId": "PROJ-001",
        "siteWorkerId": "worker-a",
        "reportDate": "2026-11-20",
        "workDescription": "測試用日報",
        "workerCount": 5,
        "weatherCondition": "Sunny",
        "status": "Submitted",
        "createdAtUtc": "2026-11-20T08:00:00",
        "rejectionReason": None,
    }
    data.update(overrides)
    return Report.from_json(data)


class FakeSource:
    """假的日報來源：符合 agent.tools.ReportSource 介面，不連 Azure。"""

    def __init__(self, reports: list[Report] | None = None, error: Exception | None = None) -> None:
        self.reports = reports or []
        self.error = error
        self.calls: list[str] = []

    def get_pending_reports(self) -> list[Report]:
        self.calls.append("pending")
        if self.error is not None:
            raise self.error
        return [r for r in self.reports if r.is_pending]

    def get_project_reports(self, project_id: str) -> list[Report]:
        self.calls.append(f"project:{project_id}")
        if self.error is not None:
            raise self.error
        return [r for r in self.reports if r.project_id == project_id]
