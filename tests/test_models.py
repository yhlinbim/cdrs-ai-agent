"""models.py 的單元測試：CDRS API 的 JSON → Report。"""

from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from cdrs_ai_agent.client.models import Report, ReportStatus

# 格式照 Azure 上 GET /api/v2/reports/PROJ-002 的真實回應（id 是假的）
REJECTED_JSON = {
    "id": "c54d3b5d-0000-4000-8000-000000000001",
    "projectId": "PROJ-002",
    "siteWorkerId": "worker-a",
    "reportDate": "2026-11-13",
    "workDescription": "外牆磁磚",
    "workerCount": 6,
    "weatherCondition": "Cloudy",
    "status": "Rejected",
    "createdAtUtc": "2026-11-25T03:15:30.1234567",
    "rejectionReason": "磁磚施工照片不足，請補件",
}


def test_from_json_maps_every_field() -> None:
    report = Report.from_json(REJECTED_JSON)

    assert report.id == UUID("c54d3b5d-0000-4000-8000-000000000001")
    assert report.project_id == "PROJ-002"
    assert report.report_date == date(2026, 11, 13)
    assert report.worker_count == 6
    assert report.status is ReportStatus.REJECTED
    assert report.created_at_utc == datetime(2026, 11, 25, 3, 15, 30, 123456, tzinfo=UTC)


def test_from_json_reads_rejection_reason() -> None:
    """回歸測試：曾經把 key 拼成 rejectionReaspon，退回原因永遠是 None。"""
    report = Report.from_json(REJECTED_JSON)

    assert report.rejection_reason == "磁磚施工照片不足，請補件"


def test_from_json_rejects_unknown_status() -> None:
    data = {**REJECTED_JSON, "status": "Pending"}

    with pytest.raises(ValueError, match="Pending"):
        Report.from_json(data)


def test_from_json_missing_required_field_raises_key_error() -> None:
    data = {k: v for k, v in REJECTED_JSON.items() if k != "projectId"}

    with pytest.raises(KeyError):
        Report.from_json(data)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Submitted", True),
        ("UnderReview", True),
        ("Draft", False),
        ("Approved", False),
        ("Rejected", False),
    ],
)
def test_is_pending(status: str, expected: bool) -> None:
    report = Report.from_json({**REJECTED_JSON, "status": status})

    assert report.is_pending is expected
