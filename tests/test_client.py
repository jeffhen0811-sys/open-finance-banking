from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

from scripts.config import Config
from scripts.envelope import dumps, failure_from_exception, make_envelope
from scripts.errors import PluggyError
from scripts.pluggy_client import PluggyClient


class Response:
    def __init__(self, status: int, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


class Session:
    def __init__(self, *responses):
        self.responses = deque(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response


def config(**changes):
    values = dict(client_id="visible-client", client_secret="very-secret", item_ids=("item-1",), timeout_seconds=2, max_retries=1, max_pages=5, max_provider_records=50)
    values.update(changes)
    return Config(**values)


def test_authentication_is_reused_in_process_and_timeout_is_finite():
    session = Session(
        Response(200, {"apiKey": "key-1"}),
        Response(200, {"id": "item-1"}),
        Response(200, {"id": "item-1"}),
    )
    client = PluggyClient(config(), session=session, sleeper=lambda _: None)
    client.get_item("item-1")
    client.get_item("item-1")
    assert [call[0] for call in session.calls] == ["POST", "GET", "GET"]
    assert all(call[2]["timeout"] == 2 for call in session.calls)


def test_concurrent_first_requests_share_one_authentication():
    session = Session(
        Response(200, {"apiKey": "key-1"}),
        Response(200, {"id": "item-1"}), Response(200, {"id": "item-2"}),
        Response(200, {"id": "item-3"}), Response(200, {"id": "item-4"}),
    )
    client = PluggyClient(config(), session=session, sleeper=lambda _: None)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(client.get_item, ["item-1", "item-2", "item-3", "item-4"]))
    assert {result["id"] for result in results} == {"item-1", "item-2", "item-3", "item-4"}
    assert [call[0] for call in session.calls].count("POST") == 1


def test_unauthorized_response_renews_key_once():
    session = Session(
        Response(200, {"apiKey": "key-1"}), Response(401, {}),
        Response(200, {"apiKey": "key-2"}), Response(200, {"id": "item-1"}),
    )
    client = PluggyClient(config(), session=session, sleeper=lambda _: None)
    assert client.get_item("item-1")["id"] == "item-1"
    assert [call[0] for call in session.calls] == ["POST", "GET", "POST", "GET"]


def test_authentication_retries_transient_provider_failure():
    session = Session(Response(503, {}), Response(200, {"apiKey": "key"}), Response(200, {"id": "item-1"}))
    client = PluggyClient(config(max_retries=1), session=session, sleeper=lambda _: None)
    assert client.get_item("item-1")["id"] == "item-1"
    assert [call[0] for call in session.calls] == ["POST", "POST", "GET"]


def test_retry_bound_and_structured_network_failure():
    session = Session(
        Response(200, {"apiKey": "key-1"}),
        requests.Timeout("secret should not appear"), requests.Timeout("again"),
    )
    client = PluggyClient(config(max_retries=1), session=session, sleeper=lambda _: None)
    with pytest.raises(PluggyError) as captured:
        client.get_item("item-1")
    failure = captured.value.to_failure()
    assert failure["code"] == "network_error"
    assert failure["retryable"] is True
    assert failure["resource"] == {"item_id": "item-1"}
    assert failure["details"]["attempts"] == 2


@pytest.mark.parametrize(
    "status,code,retryable",
    [(403, "authentication_error", False), (429, "rate_limit_error", True), (503, "provider_error", True)],
)
def test_http_failures_have_stable_classification(status, code, retryable):
    session = Session(Response(200, {"apiKey": "key"}), Response(status, {"clientSecret": "leak"}))
    client = PluggyClient(config(max_retries=0), session=session, sleeper=lambda _: None)
    with pytest.raises(PluggyError) as captured:
        client.get_item("item-1")
    assert captured.value.code == code
    assert captured.value.retryable is retryable
    rendered = dumps(make_envelope(failures=[failure_from_exception(captured.value)]))
    assert "very-secret" not in rendered
    assert "leak" not in rendered


def test_read_only_allowlist_rejects_mutations_and_unknown_routes():
    client = PluggyClient(config(), session=Session())
    for method, path in [("POST", "/items/item-1/update"), ("DELETE", "/items/item-1"), ("GET", "/identity")]:
        with pytest.raises(PluggyError, match="read-only") as captured:
            client.request_json(method, path)
        assert captured.value.code == "validation_error"


def test_cursor_pagination_follows_after_query(fixture_json):
    pages = fixture_json("pagination.json")
    session = Session(
        Response(200, {"apiKey": "key"}),
        Response(200, pages["cursor_first"]), Response(200, pages["cursor_last"]),
    )
    result = PluggyClient(config(), session=session, sleeper=lambda _: None).paginate_transactions("account-bank")
    assert [row["id"] for row in result.records] == ["first", "second"]
    assert session.calls[-1][2]["params"] == {"accountId": "account-bank", "after": "cursor-2"}
    assert result.truncated is False


def test_cursor_pagination_detects_repeated_continuation(fixture_json):
    first = fixture_json("pagination.json")["cursor_first"]
    session = Session(Response(200, {"apiKey": "key"}), Response(200, first), Response(200, first))
    result = PluggyClient(config(), session=session, sleeper=lambda _: None).paginate_transactions("account-bank")
    assert result.truncated is True
    assert result.metadata["reason"] == "repeated_continuation"


def test_cursor_pagination_stops_early_at_output_limit(fixture_json):
    first = fixture_json("pagination.json")["cursor_first"]
    session = Session(Response(200, {"apiKey": "key"}), Response(200, first))
    result = PluggyClient(config(), session=session, sleeper=lambda _: None).paginate_transactions("account-bank", stop_after=1)
    assert len(result.records) == 1
    assert result.metadata["reason"] == "output_limit"


def test_page_pagination_traverses_total_pages(fixture_json):
    pages = fixture_json("pagination.json")
    session = Session(
        Response(200, {"apiKey": "key"}),
        Response(200, pages["page_first"]), Response(200, pages["page_last"]),
    )
    result = PluggyClient(config(), session=session, sleeper=lambda _: None).list_accounts("item-1")
    assert [row["id"] for row in result.records] == ["first", "second"]
    assert [call[2].get("params", {}).get("page") for call in session.calls[1:]] == [1, 2]


def test_page_pagination_exposes_safety_cap(fixture_json):
    first = fixture_json("pagination.json")["page_first"]
    session = Session(Response(200, {"apiKey": "key"}), Response(200, first))
    result = PluggyClient(config(max_pages=1), session=session, sleeper=lambda _: None).list_accounts("item-1")
    assert result.truncated is True
    assert result.metadata["reason"] == "max_pages"


def test_page_pagination_detects_repeated_provider_page(fixture_json):
    first = fixture_json("pagination.json")["page_first"]
    session = Session(
        Response(200, {"apiKey": "key"}), Response(200, first), Response(200, first)
    )
    result = PluggyClient(config(), session=session, sleeper=lambda _: None).list_accounts("item-1")
    assert result.truncated is True
    assert result.metadata["reason"] == "repeated_page"


def test_malformed_page_number_is_classified_as_pagination_error():
    session = Session(
        Response(200, {"apiKey": "key"}),
        Response(200, {"page": "not-a-number", "totalPages": 2, "results": []}),
    )
    client = PluggyClient(config(), session=session, sleeper=lambda _: None)
    with pytest.raises(PluggyError) as captured:
        client.list_accounts("item-1")
    assert captured.value.code == "pagination_error"
