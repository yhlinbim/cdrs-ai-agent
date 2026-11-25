"""CDRS REST API 的 client（唯讀）。"""

import time
from typing import Any
from urllib.parse import quote

import httpx

from cdrs_ai_agent.client.config import CdrsSettings
from cdrs_ai_agent.client.models import Report

# token 到期前多少秒就先重新取，避免剛好在請求途中過期
_TOKEN_REFRESH_MARGIN_SECONDS = 300


class CdrsClient:
    """呼叫 CDRS REST API v2。"""

    def __init__(self, settings: CdrsSettings, http_client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._http = http_client or httpx.Client(
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
        )
        self._token: str | None = None
        self._token_expires_at = 0.0

    def get_pending_reports(self) -> list[Report]:
        """所有待簽核（Submitted、UnderReview）的日報，不分工地。"""
        return [Report.from_json(d) for d in self._get_json("/api/v2/reports/pending")]

    def get_project_reports(self, project_id: str) -> list[Report]:
        """某工地的所有日報，包含各種狀態。"""
        path = f"/api/v2/reports/{quote(project_id, safe='')}"
        return [Report.from_json(d) for d in self._get_json(path)]

    def _get_token(self) -> str:
        now = time.monotonic()
        if self._token is not None and now < self._token_expires_at:
            return self._token

        resp = self._http.post(
            "/api/auth/token",
            json={"username": self._settings.username, "role": self._settings.role},
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["token"]
        self._token_expires_at = now + body["expires_in"] - _TOKEN_REFRESH_MARGIN_SECONDS
        return self._token

    def _get_json(self, path: str) -> list[dict[str, Any]]:
        resp = self._http.get(path, headers={"Authorization": f"Bearer {self._get_token()}"})
        resp.raise_for_status()
        return resp.json()