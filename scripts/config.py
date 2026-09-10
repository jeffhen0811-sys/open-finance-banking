"""Environment-based configuration for Pluggy read-only queries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from .errors import ConfigurationError


def _positive_number(
    environment: Mapping[str, str], name: str, default: float, *, integer: bool = False
) -> float | int:
    raw = environment.get(name, str(default))
    try:
        value = int(raw) if integer else float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be a positive number.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return value


def _nonnegative_integer(environment: Mapping[str, str], name: str, default: int) -> int:
    raw = environment.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be a non-negative integer.") from exc
    if value < 0:
        raise ConfigurationError(f"{name} must be a non-negative integer.")
    return value


@dataclass(frozen=True)
class Config:
    client_id: str
    client_secret: str
    item_ids: tuple[str, ...]
    base_url: str = "https://api.pluggy.ai"
    timeout_seconds: float = 30.0
    max_retries: int = 2
    max_pages: int = 50
    max_provider_records: int = 5000
    max_workers: int = 4

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> "Config":
        env = os.environ if environment is None else environment
        client_id = env.get("PLUGGY_CLIENT_ID", "").strip()
        client_secret = env.get("PLUGGY_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            raise ConfigurationError(
                "PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET must be configured."
            )

        raw_ids = env.get("PLUGGY_ITEM_IDS", "").strip()
        if not raw_ids:
            raw_ids = env.get("PLUGGY_ITEM_ID", "").strip()
        item_ids = tuple(dict.fromkeys(part.strip() for part in raw_ids.split(",") if part.strip()))
        if not item_ids:
            raise ConfigurationError(
                "PLUGGY_ITEM_IDS must contain at least one Item identifier; "
                "PLUGGY_ITEM_ID is accepted temporarily as a single-Item fallback."
            )

        max_retries = _nonnegative_integer(env, "PLUGGY_MAX_RETRIES", 2)
        max_workers = int(_positive_number(env, "PLUGGY_MAX_WORKERS", 4, integer=True))
        if max_workers > 4:
            raise ConfigurationError("PLUGGY_MAX_WORKERS cannot exceed 4.")

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            item_ids=item_ids,
            base_url=env.get("PLUGGY_BASE_URL", "https://api.pluggy.ai").rstrip("/"),
            timeout_seconds=float(_positive_number(env, "PLUGGY_TIMEOUT_SECONDS", 30.0)),
            max_retries=max_retries,
            max_pages=int(_positive_number(env, "PLUGGY_MAX_PAGES", 50, integer=True)),
            max_provider_records=int(
                _positive_number(env, "PLUGGY_MAX_PROVIDER_RECORDS", 5000, integer=True)
            ),
            max_workers=max_workers,
        )
