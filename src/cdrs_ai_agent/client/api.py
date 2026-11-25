"""CDRS REST API 的 client（唯讀）。"""

import time
from typing import Any
from urllib.parse import quote

import httpx

from cdrs_ai_agent.client.config import CdrsSettings
from cdrs_ai_agent.client.errors import (
    CdrsApiError,
    CdrsAuthError,
    CdrsError,
    CdrsRateLimitedError,
)
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

        resp = self._send(
            "POST",
            "/api/auth/token",
            json={"username": self._settings.username, "role": self._settings.role},
        )
        if resp.status_code in (400, 401, 403):
            raise CdrsAuthError(f"Token request rejected ({resp.status_code}): {_error_message(resp)}")
        _raise_for_error(resp)

        body = resp.json()
        self._token = body["token"]
        self._token_expires_at = now + body["expires_in"] - _TOKEN_REFRESH_MARGIN_SECONDS
        return self._token

    def _get_json(self, path: str) -> list[dict[str, Any]]:
        resp = self._authorized_get(path)
        if resp.status_code == 401:
            # 快取的 token 被拒絕（例如伺服器換了簽章金鑰）：清掉快取，重新登入後再試一次
            self._token = None
            resp = self._authorized_get(path)
        _raise_for_error(resp)
        return resp.json()

    def _authorized_get(self, path: str) -> httpx.Response:
        return self._send("GET", path, headers={"Authorization": f"Bearer {self._get_token()}"})

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """發出請求；網路層的錯誤轉成 CdrsError。"""
        try:
            return self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as e:
            raise CdrsError(
                f"CDRS did not respond within {self._settings.timeout_seconds}s"
            ) from e
        except httpx.TransportError as e:
            raise CdrsError(f"Cannot reach CDRS: {e}") from e


def _error_message(resp: httpx.Response) -> str:
    """從錯誤回應取出訊息；CDRS 的錯誤格式是 {"status", "error", "correlationId"}。"""
    try:
        return str(resp.json().get("error", resp.text))
    except ValueError:
        return resp.text


def _raise_for_error(resp: httpx.Response) -> None:
    """把 4xx／5xx 轉成對應的 CDRS 例外。"""
    if resp.is_success:
        return
    if resp.status_code in (401, 403):
        raise CdrsAuthError(f"CDRS rejected the request ({resp.status_code}): {_error_message(resp)}")
    if resp.status_code == 429:
        raise CdrsRateLimitedError(int(resp.headers.get("Retry-After", "60")))
    raise CdrsApiError(
        resp.status_code,
        _error_message(resp),
        correlation_id=resp.headers.get("X-Correlation-ID"),
    )