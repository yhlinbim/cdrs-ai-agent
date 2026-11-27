"""CDRS 施工日報的 MCP server：把 agent 的工具透過 MCP 提供給任何 MCP host。"""

from datetime import date
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from cdrs_ai_agent.agent.tools import ReportSource, ToolExecutor

INSTRUCTIONS = (
    "查詢營造業施工日報的簽核狀況。所有工具都是唯讀的。"
    "需要日報資料時請使用工具，不要猜測；工具查不到就照實說。"
    "如果問題含糊，或工具只能回答一部分，要先說明限制或請使用者澄清。"
)


def create_server(source: ReportSource) -> MCPServer:
    """建立 MCP server；資料來源由外部傳入（正式用 CdrsClient，測試用假的）。"""
    mcp = MCPServer("cdrs-reports", instructions=INSTRUCTIONS)

    def run(name: str, tool_input: dict[str, Any]) -> str:
        # 每次呼叫都取今天：server 可能連續開好幾天
        result = ToolExecutor(source, date.today()).execute(name, tool_input)
        if result.is_error:
            raise ToolError(result.content)
        return result.content

    @mcp.tool()
    def get_pending_reports(
        older_than_days: Annotated[
            int | None,
            Field(
                ge=0,
                description=(
                    "只回傳「已經待簽超過」這個天數的日報（日報日期早於今天減 N 天），"
                    "例如 5 表示待簽超過 5 天。注意：這不是「最近 N 天」。"
                ),
            ),
        ] = None,
    ) -> str:
        """只取得「等待主管簽核」的施工日報（狀態 Submitted 或 UnderReview）。

        不包含草稿、已核准、已退回的。使用者問到待簽、待審核、拖太久沒簽的日報時使用。
        要查某個工地全部的日報（含已核准、已退回），請改用 get_project_reports。
        """
        tool_input = {} if older_than_days is None else {"older_than_days": older_than_days}
        return run("get_pending_reports", tool_input)

    @mcp.tool()
    def get_project_reports(
        project_id: Annotated[str, Field(description="工地代號，例如 PROJ-001")],
    ) -> str:
        """取得某個工地的所有施工日報，包含草稿、已核准與已退回的（退回的會附上退回原因）。"""
        return run("get_project_reports", {"project_id": project_id})

    return mcp
