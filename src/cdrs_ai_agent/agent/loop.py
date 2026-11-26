"""Agent loop：讓 Claude 反覆使用工具，直到能回答使用者的問題。"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from anthropic import Anthropic

from cdrs_ai_agent.agent.tools import TOOL_DEFINITIONS, ToolExecutor

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TURNS = 5

SYSTEM_TEMPLATE = (
    "你是營造業的工地助理，協助主管掌握施工日報的簽核狀況。"
    "今天是 {today}。"
    "需要日報資料時一定要用工具查詢，不要自己猜；工具查不到或發生錯誤就照實說。"
    "用繁體中文回答，不要使用 Markdown 格式，回答簡短。"
)


@dataclass(frozen=True, slots=True)
class AgentAnswer:
    """一次提問的結果，連同用了多少資源。"""

    text: str
    turns: int
    tool_calls: int
    input_tokens: int
    output_tokens: int


class ReportAgent:
    """施工日報助理：把使用者的問題交給 Claude，需要資料時執行工具。"""

    def __init__(
        self,
        client: Anthropic,
        executor: ToolExecutor,
        today: date,
        model: str = DEFAULT_MODEL,
        max_turns: int = MAX_TURNS,
    ) -> None:
        self._client = client
        self._executor = executor
        self._model = model
        self._max_turns = max_turns
        self._system = SYSTEM_TEMPLATE.format(today=today.isoformat())

    def ask(self, question: str) -> AgentAnswer:
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        input_tokens = output_tokens = tool_calls = 0

        for turn in range(1, self._max_turns + 1):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=self._system,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
            input_tokens += response.usage.input_tokens
            output_tokens += response.usage.output_tokens
            logger.info("Turn %d: stop_reason=%s", turn, response.stop_reason)

            if response.stop_reason != "tool_use":
                text = "".join(b.text for b in response.content if b.type == "text")
                if response.stop_reason == "max_tokens":
                    text += "（回答過長，已被截斷）"
                return AgentAnswer(text, turn, tool_calls, input_tokens, output_tokens)

            messages.append({"role": "assistant", "content": response.content})
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = self._executor.execute(block.name, block.input)
                tool_calls += 1
                logger.info("Tool %s %s -> is_error=%s", block.name, block.input, result.is_error)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.content,
                        "is_error": result.is_error,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        logger.warning("Agent stopped after %d turns without a final answer", self._max_turns)
        return AgentAnswer(
            "抱歉，查詢步驟太多，沒有在限制內完成。請把問題問得更具體一點。",
            self._max_turns,
            tool_calls,
            input_tokens,
            output_tokens,
        )
