# cdrs-ai-agent

[![CI](https://github.com/yhlinbim/cdrs-ai-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/yhlinbim/cdrs-ai-agent/actions/workflows/ci.yml)

A tool-using LLM agent that answers questions about construction daily reports, built on top of the
[CDRS](https://github.com/yhlinbim/construction-daily-report-system) REST API
(ASP.NET Core 8 on Azure App Service).

Ask in plain language. The agent decides which read-only tools to call, fetches real data from CDRS,
and answers from that data instead of guessing.

## Example

Question: *"Which project has the most pending reports, and has it ever had a report rejected?"*

```text
$ uv run python -m cdrs_ai_agent.agent "待簽的日報裡哪個工地最多？那個工地有沒有被退回過的日報？"
INFO cdrs_ai_agent.agent.loop: Turn 1: stop_reason=tool_use
INFO cdrs_ai_agent.agent.loop: Tool get_pending_reports {} -> is_error=False
INFO cdrs_ai_agent.agent.loop: Turn 2: stop_reason=tool_use
INFO cdrs_ai_agent.agent.loop: Tool get_project_reports {'project_id': 'PROJ-001'} -> is_error=False
INFO cdrs_ai_agent.agent.loop: Turn 3: stop_reason=end_turn
待簽的日報裡 PROJ-001 工地最多，有 2 份待簽。查詢結果顯示 PROJ-001 沒有被退回過的日報，只有 2 份待簽核和 1 份草稿。

（呼叫 Claude 3 次、執行工具 2 次；input 4974／output 253 tokens）
```

The agent planned the two steps on its own: list the pending reports, work out which project has
the most, then fetch that project's full history.

## Architecture

```text
agent/__main__.py      entry point: loads .env, configures logging, wires everything up
└── ReportAgent        agent loop (agent/loop.py) ───────────── Anthropic Messages API
    └── ToolExecutor   tools (agent/tools.py)
        └── ReportSource (Protocol)
            └── CdrsClient   REST client (client/api.py) ───── CDRS API on Azure
```

| Layer | Responsibility |
|---|---|
| `client/` | CDRS REST client: JWT caching (refreshed 5 minutes early), one retry on 401, typed exceptions (`CdrsAuthError`, `CdrsRateLimitedError`, `CdrsApiError`) carrying status codes and correlation IDs; an immutable `Report` model; pure query functions |
| `agent/tools.py` | Two read-only tools. Validates input before calling CDRS, returns only the fields needed to answer, and turns empty results and errors into explicit messages (`is_error`) |
| `agent/loop.py` | Calls Claude while `stop_reason == "tool_use"`, runs every requested tool and returns all results in one message, stops after 5 turns, and reports token usage |

## Design decisions

- **Read-only, allow-listed tools.** The model can only request tools that exist in the executor's
  table; anything else (for example `approve_report`) is rejected. Write actions would need human
  confirmation.
- **Grounding over guessing.** The system prompt tells the model to use tools for any report data
  and includes today's date, which the model cannot know on its own. Empty results come back as
  sentences rather than `[]`.
- **Data minimisation.** Tool results drop internal IDs, worker IDs and timestamps the model does
  not need to answer.
- **Errors do not crash the loop.** Permission and API errors become tool results flagged
  `is_error`, so the model can explain what went wrong.
- **Bounded cost.** At most 5 turns per question; token usage is reported for every run.

## Getting started

Requirements: [uv](https://docs.astral.sh/uv/), an Anthropic API key, and access to a CDRS instance.

```bash
uv sync
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
# fill in CDRS_BASE_URL, CDRS_USERNAME, CDRS_ROLE and ANTHROPIC_API_KEY
uv run python -m cdrs_ai_agent.agent "哪些日報待簽超過 5 天？"
```

The demo backend runs on the Azure App Service free tier and can take 20–60 seconds to wake up.
Open `/health/ready` first.

## Development

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

The 37 tests run without network access or API keys. Claude is replaced by a scripted fake client
and CDRS by an in-memory source implementing `ReportSource`; the project's own code runs for real.
They cover JSON mapping (including a regression test for a past field-name typo), query boundaries,
tool validation and data minimisation, and loop behaviour: message order, `tool_use_id` matching,
several tool calls in one response, the turn limit and truncated answers.

GitHub Actions runs ruff and pytest on every push and pull request.

## Known limitations

- CDRS currently uses a demo login that lets the caller choose a role. Until server-side
  authentication is in place, the agent's permissions are only as strong as that demo login.
- Answer quality has not been evaluated systematically yet; the tests check how the program
  handles model responses, not how good the answers are.

## Roadmap

- MCP server exposing the same tools
- `httpx.MockTransport` tests for `CdrsClient` (token caching, 401 retry, error mapping)
- A small evaluation set of questions with known answers
