"""執行方式：uv run python -m cdrs_ai_agent.mcp_server（stdio，通常由 MCP host 啟動）"""

import logging
import sys

from dotenv import load_dotenv

from cdrs_ai_agent.client.api import CdrsClient
from cdrs_ai_agent.client.config import CdrsSettings
from cdrs_ai_agent.mcp_server.server import create_server


def main() -> None:
    load_dotenv()
    # stdout 是 MCP 協定的通道：log 一律寫到 stderr
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    with CdrsClient(CdrsSettings.from_env()) as cdrs:
        create_server(cdrs).run()


if __name__ == "__main__":
    main()
