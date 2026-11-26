"""執行方式：uv run python -m cdrs_ai_agent.agent "哪些日報待簽超過 5 天？" """

import logging
import sys
from datetime import date

from anthropic import Anthropic
from dotenv import load_dotenv

from cdrs_ai_agent.agent.loop import ReportAgent
from cdrs_ai_agent.agent.tools import ToolExecutor
from cdrs_ai_agent.client.api import CdrsClient
from cdrs_ai_agent.client.config import CdrsSettings


def main() -> int:
    if len(sys.argv) < 2:
        print('用法：uv run python -m cdrs_ai_agent.agent "你的問題"', file=sys.stderr)
        return 2
    question = " ".join(sys.argv[1:])

    load_dotenv()
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("cdrs_ai_agent").setLevel(logging.INFO)

    today = date.today()
    with CdrsClient(CdrsSettings.from_env()) as cdrs:
        agent = ReportAgent(Anthropic(), ToolExecutor(cdrs, today), today)
        answer = agent.ask(question)

    print(answer.text)
    print(
        f"\n（呼叫 Claude {answer.turns} 次、執行工具 {answer.tool_calls} 次；"
        f"input {answer.input_tokens}／output {answer.output_tokens} tokens）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
