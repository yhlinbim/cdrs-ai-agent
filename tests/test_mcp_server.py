"""mcp_server 的測試：用 MCP 官方的 in-memory Client 連到 server，不連 Azure、不花 token。"""

import json

import pytest
from mcp import Client

from cdrs_ai_agent.client.errors import CdrsAuthError
from cdrs_ai_agent.mcp_server.server import create_server
from tests.helpers import FakeSource, make_report

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_lists_both_read_only_tools() -> None:
    async with Client(create_server(FakeSource())) as client:
        result = await client.list_tools()

    names = sorted(tool.name for tool in result.tools)
    assert names == ["get_pending_reports", "get_project_reports"]


async def test_get_project_reports_returns_minimal_fields() -> None:
    source = FakeSource(
        [make_report(projectId="PROJ-002", status="Rejected", rejectionReason="照片不足")]
    )

    async with Client(create_server(source)) as client:
        result = await client.call_tool("get_project_reports", {"project_id": "PROJ-002"})

    assert not result.is_error
    report = json.loads(result.content[0].text)[0]
    assert report["rejection_reason"] == "照片不足"
    assert "site_worker_id" not in report


async def test_blank_project_id_becomes_tool_error_without_calling_cdrs() -> None:
    source = FakeSource()

    async with Client(create_server(source)) as client:
        result = await client.call_tool("get_project_reports", {"project_id": "   "})

    assert result.is_error
    assert "工地代號" in result.content[0].text
    assert source.calls == []


async def test_negative_days_rejected_by_schema_before_calling_cdrs() -> None:
    source = FakeSource()

    async with Client(create_server(source)) as client:
        result = await client.call_tool("get_pending_reports", {"older_than_days": -1})

    assert result.is_error
    assert source.calls == []


async def test_permission_error_becomes_tool_error() -> None:
    source = FakeSource(error=CdrsAuthError("403"))

    async with Client(create_server(source)) as client:
        result = await client.call_tool("get_pending_reports", {})

    assert result.is_error
    assert "沒有權限" in result.content[0].text
