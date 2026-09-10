from __future__ import annotations

import json

import pytest

from scripts.config import Config
from scripts.envelope import dumps, make_envelope
from scripts.errors import ConfigurationError


def base_env(**overrides: str) -> dict[str, str]:
    values = {
        "PLUGGY_CLIENT_ID": "client-for-test",
        "PLUGGY_CLIENT_SECRET": "secret-for-test",
        "PLUGGY_ITEM_IDS": "item-1,item-2,item-1",
    }
    values.update(overrides)
    return values


def test_configuration_loads_all_bounds_and_deduplicates_items():
    config = Config.from_env(base_env(
        PLUGGY_TIMEOUT_SECONDS="5.5",
        PLUGGY_MAX_RETRIES="0",
        PLUGGY_MAX_PAGES="7",
        PLUGGY_MAX_PROVIDER_RECORDS="900",
        PLUGGY_MAX_WORKERS="3",
    ))
    assert config.item_ids == ("item-1", "item-2")
    assert config.timeout_seconds == 5.5
    assert config.max_retries == 0
    assert config.max_pages == 7
    assert config.max_provider_records == 900
    assert config.max_workers == 3


def test_configuration_accepts_temporary_single_item_fallback():
    env = base_env(PLUGGY_ITEM_IDS="", PLUGGY_ITEM_ID="legacy-item")
    assert Config.from_env(env).item_ids == ("legacy-item",)


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"PLUGGY_CLIENT_ID": ""}, "PLUGGY_CLIENT_ID"),
        ({"PLUGGY_ITEM_IDS": "", "PLUGGY_ITEM_ID": ""}, "PLUGGY_ITEM_IDS"),
        ({"PLUGGY_TIMEOUT_SECONDS": "never"}, "PLUGGY_TIMEOUT_SECONDS"),
        ({"PLUGGY_MAX_WORKERS": "5"}, "cannot exceed 4"),
    ],
)
def test_configuration_errors_are_actionable(overrides, message):
    with pytest.raises(ConfigurationError, match=message):
        Config.from_env(base_env(**overrides))


def test_envelope_statuses_and_deterministic_serialization():
    success = make_envelope([{"id": "one"}])
    partial = make_envelope([{"id": "one"}], [{"code": "provider_error"}])
    error = make_envelope(failures=[{"code": "provider_error"}])
    assert success["status"] == "success"
    assert partial["status"] == "partial"
    assert error["status"] == "error"
    assert dumps(success) == dumps(success)
    assert json.loads(dumps(success)) == success


def test_raw_and_failure_values_are_recursively_redacted():
    document = make_envelope(
        [{"raw": {"apiKey": "do-not-leak", "nested": {"clientSecret": "hidden"}}}],
        [{"code": "x", "details": {"authorization": "Bearer hidden"}}],
    )
    rendered = dumps(document)
    assert "do-not-leak" not in rendered
    assert "Bearer hidden" not in rendered
    assert rendered.count("[REDACTED]") == 3


def test_pagination_metadata_compacts_normal_single_page_reads():
    document = make_envelope(
        pagination=[
            {
                "item_id": "item-1",
                "source_kind": "account_discovery",
                "kind": "page",
                "pages_read": 1,
                "reason": None,
            },
            {
                "account_id": "account-1",
                "source_kind": "account_transaction",
                "kind": "cursor",
                "pages_read": 1,
                "reason": None,
            },
            {
                "investment_id": "investment-1",
                "source_kind": "investment_movement",
                "kind": "page",
                "pages_read": 1,
                "reason": None,
            },
        ]
    )

    assert document["meta"]["pagination"] == []
    assert document["meta"]["pagination_summary"] == {
        "resources_read": 3,
        "pages_read": 3,
        "multi_page_resources": 0,
        "truncated_resources": 0,
        "by_kind": {"cursor": 1, "page": 2},
        "by_source_kind": {
            "account_discovery": 1,
            "account_transaction": 1,
            "investment_movement": 1,
        },
    }


def test_pagination_metadata_keeps_only_actionable_details():
    multi_page = {
        "account_id": "account-1",
        "source_kind": "account_transaction",
        "kind": "cursor",
        "pages_read": 2,
        "reason": None,
    }
    truncated = {
        "investment_id": "investment-1",
        "source_kind": "investment_movement",
        "kind": "page",
        "pages_read": 1,
        "reason": "max_pages",
    }
    document = make_envelope(
        pagination=[
            multi_page,
            truncated,
            {
                "investment_id": "investment-2",
                "source_kind": "investment_movement",
                "kind": "page",
                "pages_read": 1,
                "reason": None,
            },
        ]
    )

    assert document["meta"]["pagination"] == [multi_page, truncated]
    assert document["meta"]["pagination_summary"] == {
        "resources_read": 3,
        "pages_read": 4,
        "multi_page_resources": 1,
        "truncated_resources": 1,
        "by_kind": {"cursor": 1, "page": 2},
        "by_source_kind": {
            "account_transaction": 1,
            "investment_movement": 2,
        },
    }
