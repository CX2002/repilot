from __future__ import annotations
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    api_key: str | None = os.getenv("REPILOT_API_KEY")
    base_url: str = os.getenv("REPILOT_BASE_URL", "https://api.deepseek.com/v1")
    model: str = os.getenv("REPILOT_MODEL", "deepseek-chat")
    max_rounds: int = int(os.getenv("REPILOT_MAX_ROUNDS", "6"))
    test_timeout: int = int(os.getenv("REPILOT_TEST_TIMEOUT", "60"))
    trace_dir: str = os.getenv("REPILOT_TRACE_DIR", ".repilot/traces")
    allowed_roots: tuple[str, ...] = tuple(x.strip() for x in os.getenv("REPILOT_ALLOWED_ROOTS", "").split(",") if x.strip())

settings = Settings()
