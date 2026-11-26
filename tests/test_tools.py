"""agent/tools.py 的單元測試：用假的資料來源，不連 Azure。"""

import json
from datetime import date

import pytest

from cdrs_ai_agent.agent.tools import ToolExecutor
from cdrs_ai_agent.client.errors import CdrsApiError, CdrsAuthError
from tests.helpers import FakeSource, make_report

TODAY = date(2026, 11, 26)


def test_unknown_tool_returns_error_without_calling_cdrs() -> None:
    source = FakeSource()

    result = ToolExecutor(source, TODAY).execute("approve_report", {"report_id": "x"})

    assert result.is_error
    assert "approve_report" in result.content
    assert source.calls == []


def test_project_reports_keep_reason_and_drop_internal_fields() -> None:
    source = FakeSource(
        [make_report(projectId="PROJ-002", status="Rejected", rejectionReason="照片不足")]
    )

    result = ToolExecutor(source, TODAY).execute("get_project_reports", {"project_id": "PROJ-002"})

    report = json.loads(result.content)[0]
    assert report["rejection_reason"] == "照片不足"
    assert "id" not in report
    assert "site_worker_id" not in report


def test_pending_reports_filtered_by_older_than_days() -> None:
    source = FakeSource(
        [
            make_report(reportDate="2026-11-24"),
            make_report(reportDate="2026-11-17"),
            make_report(reportDate="2026-11-01", status="Approved"),
        ]
    )

    result = ToolExecutor(source, TODAY).execute("get_pending_reports", {"older_than_days": 5})

    assert [r["report_date"] for r in json.loads(result.content)] == ["2026-11-17"]


def test_empty_result_returns_a_sentence_not_an_empty_list() -> None:
    result = ToolExecutor(FakeSource(), TODAY).execute(
        "get_project_reports", {"project_id": "PROJ-999"}
    )

    assert not result.is_error
    assert "沒有任何日報" in result.content


@pytest.mark.parametrize(
    "tool_input",
    [{}, {"project_id": ""}, {"project_id": "   "}, {"project_id": 123}],
)
def test_invalid_project_id_is_rejected_before_calling_cdrs(tool_input: dict[str, object]) -> None:
    source = FakeSource()

    result = ToolExecutor(source, TODAY).execute("get_project_reports", tool_input)

    assert result.is_error
    assert source.calls == []


@pytest.mark.parametrize("days", [-1, "5"])
def test_invalid_older_than_days_is_rejected_before_calling_cdrs(days: object) -> None:
    source = FakeSource()

    result = ToolExecutor(source, TODAY).execute("get_pending_reports", {"older_than_days": days})

    assert result.is_error
    assert source.calls == []


def test_permission_error_becomes_a_friendly_message() -> None:
    source = FakeSource(error=CdrsAuthError("CDRS rejected the request (403)"))

    result = ToolExecutor(source, TODAY).execute("get_pending_reports", {})

    assert result.is_error
    assert result.content == "目前的帳號沒有權限查詢這項資料。"


def test_other_cdrs_errors_are_reported_as_tool_errors() -> None:
    source = FakeSource(error=CdrsApiError(500, "Internal Server Error", correlation_id="abc-123"))

    result = ToolExecutor(source, TODAY).execute("get_project_reports", {"project_id": "PROJ-001"})

    assert result.is_error
    assert "CDRS" in result.content
