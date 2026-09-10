"""Stable, secret-safe errors exposed by the CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


SENSITIVE_KEYS = {
    "authorization",
    "clientid",
    "clientsecret",
    "client_id",
    "client_secret",
    "x-api-key",
    "apikey",
    "api_key",
    "token",
}


def redact(value: Any) -> Any:
    """Recursively redact authentication material from serializable values."""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    return value


@dataclass
class PluggyError(Exception):
    """An expected error with a stable machine-readable representation."""

    code: str
    message: str
    retryable: bool = False
    resource: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def to_failure(self) -> dict[str, Any]:
        failure: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "resource": redact(self.resource),
        }
        if self.details:
            failure["details"] = redact(self.details)
        return failure


class ConfigurationError(PluggyError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__("configuration_error", message, False, details=details or {})


class ValidationError(PluggyError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__("validation_error", message, False, details=details or {})


class PaginationError(PluggyError):
    def __init__(self, message: str, *, resource: dict[str, Any] | None = None):
        super().__init__("pagination_error", message, False, resource or {})
