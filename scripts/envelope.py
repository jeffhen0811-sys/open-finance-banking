"""Stable response-envelope construction and deterministic JSON serialization."""

from __future__ import annotations

import json
from typing import Any, Iterable

from .errors import PluggyError, redact


def failure_from_exception(error: BaseException, **resource: Any) -> dict[str, Any]:
    if isinstance(error, PluggyError):
        if resource and not error.resource:
            error.resource = resource
        return error.to_failure()
    return PluggyError(
        "unexpected_response",
        "An unexpected response prevented this resource from being read.",
        False,
        resource,
    ).to_failure()


def _pagination_metadata(pages: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_source_kind: dict[str, int] = {}
    actionable: list[dict[str, Any]] = []
    pages_read = 0
    multi_page_resources = 0
    truncated_resources = 0

    for page in pages:
        page_count = page.get("pages_read", 0)
        page_count = page_count if isinstance(page_count, int) else 0
        reason = page.get("reason")
        kind = str(page.get("kind") or "unknown")
        source_kind = str(page.get("source_kind") or "unspecified")

        pages_read += page_count
        by_kind[kind] = by_kind.get(kind, 0) + 1
        by_source_kind[source_kind] = by_source_kind.get(source_kind, 0) + 1
        if page_count > 1:
            multi_page_resources += 1
        if reason is not None:
            truncated_resources += 1
        if page_count > 1 or reason is not None:
            actionable.append(page)

    return {
        "pagination_summary": {
            "resources_read": len(pages),
            "pages_read": pages_read,
            "multi_page_resources": multi_page_resources,
            "truncated_resources": truncated_resources,
            "by_kind": dict(sorted(by_kind.items())),
            "by_source_kind": dict(sorted(by_source_kind.items())),
        },
        "pagination": actionable,
    }


def make_envelope(
    items: Iterable[dict[str, Any]] = (),
    failures: Iterable[dict[str, Any]] = (),
    *,
    filters: dict[str, Any] | None = None,
    freshness: Iterable[dict[str, Any]] = (),
    pagination: Iterable[dict[str, Any]] = (),
    truncated: bool = False,
    extra_meta: dict[str, Any] | None = None,
    successful_resources: int = 0,
) -> dict[str, Any]:
    safe_items = list(redact(list(items)))
    safe_failures = list(redact(list(failures)))
    if safe_failures and (safe_items or successful_resources > 0):
        status = "partial"
    elif safe_failures:
        status = "error"
    else:
        status = "success"
    meta: dict[str, Any] = {
        "count": len(safe_items),
        "truncated": bool(truncated),
        "filters": filters or {},
        "freshness": list(redact(list(freshness))),
    }
    pages = list(redact(list(pagination)))
    if pages:
        meta.update(_pagination_metadata(pages))
    if extra_meta:
        meta.update(redact(extra_meta))
    return {"status": status, "items": safe_items, "meta": meta, "failures": safe_failures}


def dumps(document: dict[str, Any]) -> str:
    return json.dumps(redact(document), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
