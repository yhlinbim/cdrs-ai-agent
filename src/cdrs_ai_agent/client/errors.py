"""CDRS client 的例外類別。"""


class CdrsError(Exception):
    """所有 CDRS client 錯誤的基底類別。"""


class CdrsAuthError(CdrsError):
    """無法取得 token，或 token 被拒絕（401／403）。"""


class CdrsRateLimitedError(CdrsError):
    """超過 CDRS 的呼叫次數上限（429）。"""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"CDRS rate limit exceeded; retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class CdrsApiError(CdrsError):
    """CDRS 回傳的其他錯誤（4xx／5xx）。"""

    def __init__(self, status_code: int, message: str, correlation_id: str | None = None) -> None:
        super().__init__(f"CDRS API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.correlation_id = correlation_id