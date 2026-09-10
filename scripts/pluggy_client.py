"""Direct, read-only Pluggy REST client."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

import requests

from .config import Config
from .errors import PaginationError, PluggyError


_READ_ONLY_ROUTES = (
    re.compile(r"^/items/[^/]+$"),
    re.compile(r"^/accounts$"),
    re.compile(r"^/accounts/[^/]+$"),
    re.compile(r"^/v2/transactions$"),
    re.compile(r"^/bills$"),
    re.compile(r"^/investments$"),
    re.compile(r"^/investments/[^/]+$"),
    re.compile(r"^/investments/[^/]+/transactions$"),
)


@dataclass
class PageResult:
    records: list[dict[str, Any]]
    truncated: bool
    metadata: dict[str, Any]


class PluggyClient:
    def __init__(
        self,
        config: Config,
        *,
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()
        self._sleep = sleeper
        self._api_key: str | None = None
        self._auth_lock = threading.Lock()

    def _authenticate(self) -> str:
        if self._api_key:
            return self._api_key
        with self._auth_lock:
            if self._api_key:
                return self._api_key
            return self._obtain_api_key()

    def _obtain_api_key(self) -> str:
        attempt = 0
        while True:
            try:
                response = self.session.request(
                    "POST",
                    f"{self.config.base_url}/auth",
                    json={"clientId": self.config.client_id, "clientSecret": self.config.client_secret},
                    timeout=self.config.timeout_seconds,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt < self.config.max_retries:
                    self._sleep(0.25 * (2**attempt))
                    attempt += 1
                    continue
                raise PluggyError(
                    "network_error", "Unable to reach Pluggy authentication after bounded retries.",
                    True, details={"attempts": attempt + 1},
                ) from exc
            except requests.RequestException as exc:
                raise PluggyError(
                    "network_error", "Unable to reach Pluggy authentication.", True
                ) from exc
            if (response.status_code == 429 or response.status_code >= 500) and attempt < self.config.max_retries:
                self._sleep(0.25 * (2**attempt))
                attempt += 1
                continue
            break
        if response.status_code >= 400:
            if response.status_code == 429:
                raise PluggyError(
                    "rate_limit_error", "Pluggy rate-limited authentication.", True,
                    details={"http_status": response.status_code, "attempts": attempt + 1},
                )
            raise PluggyError(
                "authentication_error",
                "Pluggy rejected the configured client credentials.",
                response.status_code >= 500,
                details={"http_status": response.status_code},
            )
        try:
            payload = response.json()
            api_key = payload["apiKey"]
        except (ValueError, KeyError, TypeError) as exc:
            raise PluggyError(
                "unexpected_response", "Pluggy authentication returned invalid JSON.", False
            ) from exc
        if not isinstance(api_key, str) or not api_key:
            raise PluggyError(
                "unexpected_response", "Pluggy authentication did not return an API key.", False
            )
        self._api_key = api_key
        return api_key

    def _invalidate_api_key(self, rejected_key: str) -> None:
        with self._auth_lock:
            if self._api_key == rejected_key:
                self._api_key = None

    @staticmethod
    def _is_allowed(method: str, path: str) -> bool:
        return method == "GET" and any(pattern.fullmatch(path) for pattern in _READ_ONLY_ROUTES)

    @staticmethod
    def _error_for_status(status: int, resource: dict[str, Any]) -> PluggyError:
        if status in (401, 403):
            return PluggyError(
                "authentication_error",
                "Pluggy did not authorize access to this resource.",
                False,
                resource,
                {"http_status": status},
            )
        if status == 404:
            return PluggyError(
                "provider_error", "The requested Pluggy resource was not found.", False,
                resource, {"http_status": status},
            )
        if status == 429:
            return PluggyError(
                "rate_limit_error", "Pluggy rate-limited the request.", True,
                resource, {"http_status": status},
            )
        if status >= 500:
            return PluggyError(
                "provider_error", "Pluggy was temporarily unable to serve the request.", True,
                resource, {"http_status": status},
            )
        return PluggyError(
            "provider_error", "Pluggy rejected the read request.", False,
            resource, {"http_status": status},
        )

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        resource: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        method = method.upper()
        if not self._is_allowed(method, path):
            raise PluggyError(
                "validation_error",
                "Only allowlisted read-only Pluggy routes can be requested.",
                False,
                resource or {"path": path},
            )

        context = resource or {"path": path}
        renewed = False
        attempt = 0
        while True:
            api_key = self._authenticate()
            try:
                response = self.session.request(
                    method,
                    f"{self.config.base_url}{path}",
                    params=params,
                    headers={"X-API-KEY": api_key, "Accept": "application/json"},
                    timeout=self.config.timeout_seconds,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt < self.config.max_retries:
                    self._sleep(0.25 * (2**attempt))
                    attempt += 1
                    continue
                raise PluggyError(
                    "network_error", "The Pluggy request failed after bounded retries.", True, context,
                    {"attempts": attempt + 1},
                ) from exc
            except requests.RequestException as exc:
                raise PluggyError(
                    "network_error", "The Pluggy request could not be completed.", True, context
                ) from exc

            if response.status_code == 401 and not renewed:
                self._invalidate_api_key(api_key)
                renewed = True
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self.config.max_retries:
                    self._sleep(0.25 * (2**attempt))
                    attempt += 1
                    continue
            if response.status_code >= 400:
                raise self._error_for_status(response.status_code, context)
            try:
                payload = response.json()
            except ValueError as exc:
                raise PluggyError(
                    "unexpected_response", "Pluggy returned a non-JSON response.", False, context
                ) from exc
            if not isinstance(payload, dict):
                raise PluggyError(
                    "unexpected_response", "Pluggy returned an unexpected JSON shape.", False, context
                )
            return payload

    def get_item(self, item_id: str) -> dict[str, Any]:
        return self.request_json("GET", f"/items/{item_id}", resource={"item_id": item_id})

    def get_account(self, account_id: str) -> dict[str, Any]:
        return self.request_json(
            "GET", f"/accounts/{account_id}", resource={"account_id": account_id}
        )

    def get_investment(self, investment_id: str) -> dict[str, Any]:
        return self.request_json(
            "GET", f"/investments/{investment_id}", resource={"investment_id": investment_id}
        )

    def paginate_v1(
        self,
        path: str,
        *,
        params: dict[str, Any],
        resource: dict[str, Any],
        stop_after: int | None = None,
    ) -> PageResult:
        records: list[dict[str, Any]] = []
        page = 1
        seen_pages: set[int] = set()
        reason: str | None = None
        while True:
            if page in seen_pages:
                reason = "repeated_page"
                break
            if len(seen_pages) >= self.config.max_pages:
                reason = "max_pages"
                break
            seen_pages.add(page)
            query = dict(params, page=page)
            payload = self.request_json("GET", path, params=query, resource=resource)
            page_records = payload.get("results", [])
            if not isinstance(page_records, list):
                raise PluggyError(
                    "unexpected_response", "Pluggy pagination results were not a list.", False, resource
                )
            records.extend(record for record in page_records if isinstance(record, dict))
            if len(records) >= self.config.max_provider_records:
                records = records[: self.config.max_provider_records]
                reason = "max_provider_records"
                break
            if stop_after is not None and len(records) >= stop_after:
                if page < int(payload.get("totalPages") or page) or len(records) > stop_after:
                    reason = "output_limit"
                records = records[:stop_after]
                break
            try:
                current = int(payload.get("page") or page)
                total = int(payload.get("totalPages") or current)
            except (TypeError, ValueError) as exc:
                raise PaginationError(
                    "Pluggy returned invalid page metadata.", resource=resource
                ) from exc
            if current >= total:
                break
            page = current + 1
        return PageResult(
            records,
            reason is not None,
            {"kind": "page", "pages_read": len(seen_pages), "reason": reason},
        )

    def paginate_transactions(
        self,
        account_id: str,
        *,
        params: dict[str, Any] | None = None,
        stop_after: int | None = None,
    ) -> PageResult:
        query: dict[str, Any] = {"accountId": account_id, **(params or {})}
        records: list[dict[str, Any]] = []
        seen_continuations: set[str] = set()
        pages = 0
        reason: str | None = None
        while True:
            if pages >= self.config.max_pages:
                reason = "max_pages"
                break
            payload = self.request_json(
                "GET", "/v2/transactions", params=query, resource={"account_id": account_id}
            )
            pages += 1
            page_records = payload.get("results", [])
            if not isinstance(page_records, list):
                raise PluggyError(
                    "unexpected_response", "Pluggy pagination results were not a list.", False,
                    {"account_id": account_id},
                )
            records.extend(record for record in page_records if isinstance(record, dict))
            if len(records) >= self.config.max_provider_records:
                records = records[: self.config.max_provider_records]
                reason = "max_provider_records"
                break
            continuation = payload.get("next")
            if stop_after is not None and len(records) >= stop_after:
                if continuation or len(records) > stop_after:
                    reason = "output_limit"
                records = records[:stop_after]
                break
            if not continuation:
                break
            if not isinstance(continuation, str):
                raise PaginationError(
                    "Pluggy returned an invalid transaction continuation.",
                    resource={"account_id": account_id},
                )
            if continuation in seen_continuations:
                reason = "repeated_continuation"
                break
            seen_continuations.add(continuation)
            parsed = urlsplit(continuation)
            next_query = dict(parse_qsl(parsed.query or continuation.lstrip("?"), keep_blank_values=True))
            if not next_query.get("after"):
                reason = "invalid_continuation"
                break
            query = next_query
        return PageResult(
            records,
            reason is not None,
            {"kind": "cursor", "pages_read": pages, "reason": reason},
        )

    def list_accounts(self, item_id: str, *, stop_after: int | None = None) -> PageResult:
        return self.paginate_v1(
            "/accounts", params={"itemId": item_id}, resource={"item_id": item_id},
            stop_after=stop_after,
        )

    def list_bills(self, account_id: str, *, stop_after: int | None = None) -> PageResult:
        return self.paginate_v1(
            "/bills", params={"accountId": account_id}, resource={"account_id": account_id},
            stop_after=stop_after,
        )

    def list_investments(self, item_id: str, *, stop_after: int | None = None) -> PageResult:
        return self.paginate_v1(
            "/investments", params={"itemId": item_id}, resource={"item_id": item_id},
            stop_after=stop_after,
        )

    def list_investments(self, item_id: str, *, stop_after: int | None = None) -> PageResult:
        return self.paginate_v1(
            "/investments", params={"itemId": item_id}, resource={"item_id": item_id},
            stop_after=stop_after,
        )

    def list_investment_transactions(
        self, investment_id: str, *, stop_after: int | None = None
    ) -> PageResult:
        return self.paginate_v1(
            f"/investments/{investment_id}/transactions",
            params={}, resource={"investment_id": investment_id}, stop_after=stop_after,
        )
