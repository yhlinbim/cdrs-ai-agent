"""Agent 的工具：給 Claude 看的定義，以及真正執行的程式。"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from cdrs_ai_agent.client.errors import CdrsAuthError, CdrsError
from cdrs_ai_agent.client.models import Report
from cdrs_ai_agent.client.queries import pending_older_than

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_pending_reports",
        "description": (
            "只取得「等待主管簽核」的施工日報（狀態 Submitted 或 UnderReview），"
            "不包含草稿、已核准、已退回的。"
            "使用者問到待簽、待審核、拖太久沒簽的日報時使用。"
            "要查某個工地全部的日報（含已核准、已退回），請改用 get_project_reports。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "older_than_days": {
                    "type": "integer",
                    "minimum": 0,
                    "description": (
                        "只回傳「已經待簽超過」這個天數的日報（日報日期早於今天減 N 天），"
                        "例如 5 表示待簽超過 5 天。注意：這不是「最近 N 天」。"
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_project_reports",
        "description": (
            "取得某個工地的所有施工日報，包含已核准與已退回的（退回的會附上退回原因）。"
            "需要工地代號，例如 PROJ-001。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "工地代號，例如 PROJ-001"},
            },
            "required": ["project_id"],
        },
    },
]


class ReportSource(Protocol):
    """工具需要的資料來源；CdrsClient 符合這個介面，測試時可以換成假的。"""

    def get_pending_reports(self) -> list[Report]: ...

    def get_project_reports(self, project_id: str) -> list[Report]: ...


@dataclass(frozen=True, slots=True)
class ToolResult:
    """一次工具執行的結果；content 會原樣放進 tool_result。"""

    content: str
    is_error: bool = False


class ToolExecutor:
    """依工具名稱執行對應的函式，並把結果轉成給 Claude 看的文字。"""

    def __init__(self, source: ReportSource, today: date) -> None:
        self._source = source
        self._today = today
        self._handlers: dict[str, Callable[[dict[str, Any]], ToolResult]] = {
            "get_pending_reports": self._get_pending_reports,
            "get_project_reports": self._get_project_reports,
        }

    def execute(self, name: str, tool_input: dict[str, Any]) -> ToolResult:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(f"沒有名為 {name} 的工具。", is_error=True)
        try:
            return handler(tool_input)
        except CdrsAuthError:
            logger.warning("Tool %s was rejected by CDRS (permission)", name)
            return ToolResult("目前的帳號沒有權限查詢這項資料。", is_error=True)
        except CdrsError as e:
            logger.warning("Tool %s failed: %s", name, e)
            return ToolResult(f"查詢 CDRS 時發生錯誤：{e}", is_error=True)

    def _get_pending_reports(self, tool_input: dict[str, Any]) -> ToolResult:
        days = tool_input.get("older_than_days")
        if days is not None and (not isinstance(days, int) or days < 0):
            return ToolResult("older_than_days 必須是 0 以上的整數。", is_error=True)
        reports = self._source.get_pending_reports()
        if days is not None:
            reports = pending_older_than(reports, days, self._today)
        if not reports:
            return ToolResult("目前沒有符合條件的待簽核日報。")
        return ToolResult(_to_json(reports))

    def _get_project_reports(self, tool_input: dict[str, Any]) -> ToolResult:
        project_id = tool_input.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            return ToolResult("需要提供工地代號 project_id，例如 PROJ-001。", is_error=True)
        reports = self._source.get_project_reports(project_id.strip())
        if not reports:
            return ToolResult(f"工地 {project_id} 目前沒有任何日報。")
        return ToolResult(_to_json(reports))


def _summarize(report: Report) -> dict[str, Any]:
    """只留下回答問題需要的欄位（資料最小化：不送 id、工人代號、建立時間）。"""
    summary: dict[str, Any] = {
        "project_id": report.project_id,
        "report_date": report.report_date.isoformat(),
        "work_description": report.work_description,
        "worker_count": report.worker_count,
        "status": report.status.value,
    }
    if report.rejection_reason:
        summary["rejection_reason"] = report.rejection_reason
    return summary


def _to_json(reports: list[Report]) -> str:
    return json.dumps([_summarize(r) for r in reports], ensure_ascii=False)
