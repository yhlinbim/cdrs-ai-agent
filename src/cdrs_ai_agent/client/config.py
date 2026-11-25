"""CDRS client 的設定，從環境變數讀取。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CdrsSettings:
    base_url: str
    username: str
    role: str
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "CdrsSettings":
        return cls(
            base_url=os.environ["CDRS_BASE_URL"].rstrip("/"),
            username=os.environ["CDRS_USERNAME"],
            role=os.environ["CDRS_ROLE"],
        )
