"""agent/loop.py 的單元測試：用假的 Claude 和假的資料來源，不花 token、不連 Azure。"""

from datetime import date
from types import SimpleNamespace
from typing import Any

from cdrs_ai_agent.agent.loop import ReportAgent
from cdrs_ai_agent.agent.tools import ToolExecutor
from cdrs_ai_agent.client.errors import CdrsAuthError
from tests.helpers import FakeSource, make_report

TODAY = date(2026, 11, 26)


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def tool_block(block_id: str, name: str, tool_input: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def response(stop_reason: str, *content: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=list(content),
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
    )


class FakeMessages:
    """照劇本依序回應的假 messages API，並記下每次收到的參數。"""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        # messages 之後還會被 append，所以存一份「當下」的副本
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses.pop(0)


class FakeAnthropic:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.messages = FakeMessages(responses)


def make_agent(
    responses: list[SimpleNamespace],
    source: FakeSource | None = None,
    max_turns: int = 5,
) -> tuple[ReportAgent, FakeAnthropic, FakeSource]:
    client = FakeAnthropic(responses)
    source = source or FakeSource()
    agent = ReportAgent(client, ToolExecutor(source, TODAY), TODAY, max_turns=max_turns)
    return agent, client, source


def test_answers_directly_without_calling_tools() -> None:
    agent, client, source = make_agent([response("end_turn", text_block("施工日報是…"))])

    answer = agent.ask("什麼是施工日報？")

    assert answer.text == "施工日報是…"
    assert (answer.turns, answer.tool_calls) == (1, 0)
    assert source.calls == []


def test_runs_tool_then_answers_with_its_result() -> None:
    source = FakeSource([make_report(reportDate="2026-11-17", workDescription="2F 柱模組立")])
    agent, client, _ = make_agent(
        [
            response(
                "tool_use", tool_block("toolu_1", "get_pending_reports", {"older_than_days": 5})
            ),
            response("end_turn", text_block("PROJ-001 有 1 筆待簽超過 5 天")),
        ],
        source,
    )

    answer = agent.ask("哪些日報待簽超過 5 天？")

    assert answer.text == "PROJ-001 有 1 筆待簽超過 5 天"
    assert (answer.turns, answer.tool_calls, answer.input_tokens) == (2, 1, 200)
    assert source.calls == ["pending"]

    second_call = client.messages.calls[1]["messages"]
    assert [m["role"] for m in second_call] == ["user", "assistant", "user"]
    tool_result = second_call[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_1"
    assert tool_result["is_error"] is False
    assert "2F 柱模組立" in tool_result["content"]


def test_multiple_tool_uses_in_one_response_are_returned_together() -> None:
    agent, client, source = make_agent(
        [
            response(
                "tool_use",
                text_block("我來查兩個工地"),
                tool_block("toolu_a", "get_project_reports", {"project_id": "PROJ-001"}),
                tool_block("toolu_b", "get_project_reports", {"project_id": "PROJ-002"}),
            ),
            response("end_turn", text_block("比較完成")),
        ]
    )

    answer = agent.ask("比較 PROJ-001 和 PROJ-002")

    last_user_message = client.messages.calls[1]["messages"][-1]
    assert [r["tool_use_id"] for r in last_user_message["content"]] == ["toolu_a", "toolu_b"]
    assert source.calls == ["project:PROJ-001", "project:PROJ-002"]
    assert answer.tool_calls == 2


def test_tool_error_is_marked_and_agent_keeps_going() -> None:
    agent, client, _ = make_agent(
        [
            response("tool_use", tool_block("toolu_1", "get_pending_reports", {})),
            response("end_turn", text_block("目前的帳號沒有權限查詢")),
        ],
        FakeSource(error=CdrsAuthError("403")),
    )

    answer = agent.ask("有哪些待簽？")

    tool_result = client.messages.calls[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True
    assert answer.text == "目前的帳號沒有權限查詢"


def test_stops_after_max_turns() -> None:
    endless = [
        response("tool_use", tool_block(f"toolu_{i}", "get_pending_reports", {})) for i in range(3)
    ]
    agent, client, _ = make_agent(endless, max_turns=3)

    answer = agent.ask("一直查")

    assert len(client.messages.calls) == 3
    assert answer.turns == 3
    assert "太多" in answer.text


def test_max_tokens_answer_is_marked_as_truncated() -> None:
    agent, _, _ = make_agent([response("max_tokens", text_block("PROJ-001 有"))])

    answer = agent.ask("列出所有日報")

    assert answer.text.endswith("（回答過長，已被截斷）")


def test_sends_today_in_system_prompt_and_both_tools() -> None:
    agent, client, _ = make_agent([response("end_turn", text_block("ok"))])

    agent.ask("嗨")

    first_call = client.messages.calls[0]
    assert "2026-11-26" in first_call["system"]
    assert [t["name"] for t in first_call["tools"]] == [
        "get_pending_reports",
        "get_project_reports",
    ]
