"""日報的查詢與統計函示 (純函式，不呼叫 API)。"""

from collections import Counter
from datetime import date

from cdrs_ai_agent.client.models import Report, ReportStatus


def filter_by_date(reports: list[Report], target: date) -> list[Report]:
    """回傳 report_date 等於 target 的日報。"""
    return [r for r in reports if r.report_date == target]


def count_by_status(reports: list[Report]) -> dict[ReportStatus, int]:
    """各狀態各有幾筆。"""
    return dict(Counter(r.status for r in reports))


def pending_older_than(reports: list[Report], days: int, today: date) -> list[Report]:
    """待簽核且 report_date 距今超過 days 天的日報，最舊的在前。"""
    overdue = [r for r in reports if r.is_pending and (today - r.report_date).days > days]
    return sorted(overdue, key=lambda r: r.report_date)


def filter_by_project(reports: list[Report], target_id: str) -> list[Report]:
    """回傳 project_id 等於 target_id 的日報。"""
    return [r for r in reports if r.project_id == target_id]


def total_workers(reports: list[Report]) -> int:
    """所有日報的出工人數加總。"""
    return sum(r.worker_count for r in reports)


def latest_report(reports: list[Report]) -> Report:
    """回傳 report_date 最新的一筆日報。"""
    return max(reports, key=lambda r: r.report_date)
