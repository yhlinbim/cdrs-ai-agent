"""queries.py 的單元測試：只測計算邏輯，不呼叫 API。"""

from datetime import date

import pytest

from cdrs_ai_agent.client.queries import (
    count_by_status,
    filter_by_project,
    latest_report,
    pending_older_than,
    total_workers,
)
from tests.helpers import make_report

TODAY = date(2026, 11, 26)


def test_filter_by_project_returns_only_matching_project() -> None:
    reports = [
        make_report(projectId="PROJ-001"),
        make_report(projectId="PROJ-002"),
        make_report(projectId="PROJ-002"),
    ]

    result = filter_by_project(reports, "PROJ-002")

    assert len(result) == 2
    assert all(r.project_id == "PROJ-002" for r in result)


def test_total_workers_sums_worker_count() -> None:
    reports = [make_report(workerCount=12), make_report(workerCount=8), make_report(workerCount=15)]

    assert total_workers(reports) == 35


def test_count_by_status_counts_each_status() -> None:
    reports = [
        make_report(status="Submitted"),
        make_report(status="Submitted"),
        make_report(status="Rejected", rejectionReason="磁磚施工照片不足"),
    ]

    assert count_by_status(reports) == {"Submitted": 2, "Rejected": 1}


@pytest.mark.parametrize(
    ("report_date", "expected_count"),
    [
        ("2026-11-20", 1),  # 6 天前：超過 5 天
        ("2026-11-21", 0),  # 剛好 5 天：不算「超過」（程式用 >）
        ("2026-11-26", 0),  # 今天
    ],
)
def test_pending_older_than_boundary(report_date: str, expected_count: int) -> None:
    reports = [make_report(reportDate=report_date)]

    assert len(pending_older_than(reports, 5, TODAY)) == expected_count


def test_pending_older_than_excludes_finished_reports_and_sorts_by_date() -> None:
    reports = [
        make_report(reportDate="2026-11-10"),
        make_report(reportDate="2026-11-01", status="Rejected", rejectionReason="照片不足"),
        make_report(reportDate="2026-11-02", status="Approved"),
        make_report(reportDate="2026-11-05"),
    ]

    result = pending_older_than(reports, 5, TODAY)

    assert [r.report_date for r in result] == [date(2026, 11, 5), date(2026, 11, 10)]


def test_latest_report_returns_most_recent() -> None:
    reports = [
        make_report(reportDate="2026-11-13"),
        make_report(reportDate="2026-11-22"),
        make_report(reportDate="2026-11-17"),
    ]

    result = latest_report(reports)

    assert result is not None
    assert result.report_date == date(2026, 11, 22)


def test_latest_report_returns_none_for_empty_list() -> None:
    assert latest_report([]) is None
