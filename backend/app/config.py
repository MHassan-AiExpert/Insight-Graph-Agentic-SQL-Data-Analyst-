"""Application settings loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "insightgraph.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM -------------------------------------------------------------
    llm_provider: Literal["groq", "scripted"] = "groq"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 45.0
    # Only used by reasoning models such as openai/gpt-oss-*: low / medium / high
    llm_reasoning_effort: str | None = "low"
    scripted_responses_path: Path | None = None

    # --- Database --------------------------------------------------------
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    query_timeout_seconds: float = 10.0
    max_result_rows: int = 500
    sample_rows_per_table: int = 3

    business_rules: str = (
        "- Revenue = SUM(order_items.quantity * order_items.unit_price * (1 - order_items.discount)) "
        "for orders with status IN ('completed','shipped'), unless the question says otherwise.\n"
        "- Cost = SUM(order_items.quantity * products.unit_cost); gross profit = revenue - cost.\n"
        "- Average order value (AOV) = revenue / number of distinct revenue orders.\n"
        "- Quarters: Q1 = Jan-Mar, Q2 = Apr-Jun, Q3 = Jul-Sep, Q4 = Oct-Dec. Data covers 2025-01-01 to 2026-10-31."
    )

    # --- Agent -----------------------------------------------------------
    max_sql_attempts: int = 3
    history_turns: int = 5
    rows_for_analysis: int = 60

    # --- API -------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
