from __future__ import annotations

import threading
import time
from collections import Counter
from copy import deepcopy

import pytest

import scripts.cli as cli
from scripts.config import Config
from scripts.errors import PluggyError
from scripts.pluggy_client import PageResult


class FakeClient:
    fixture_data = None
    failure_account = None

    def __init__(self, _config=None, fixture_json=None):
        load = fixture_json or type(self).fixture_data
        assert load is not None
        self.items = {row["id"]: row for row in load("items.json")}
        self.accounts = load("accounts.json")
        self.transactions = load("transactions.json")
        self.bills = load("bills.json")
        self.investments = load("investments.json")
        self.movements = load("investment_transactions.json")
        self.calls = Counter()

    @staticmethod
    def page(records, kind="page"):
        return PageResult(deepcopy(records), False, {"kind": kind, "pages_read": 1, "reason": None})

    def get_item(self, item_id):
        self.calls[("item", item_id)] += 1
        return deepcopy(self.items[item_id])

    def list_accounts(self, item_id):
        self.calls[("accounts", item_id)] += 1
        return self.page([row for row in self.accounts if row["itemId"] == item_id])

    def get_account(self, account_id):
        self.calls[("account", account_id)] += 1
        return deepcopy(next(row for row in self.accounts if row["id"] == account_id))

    def paginate_transactions(self, account_id, params=None, stop_after=None):
        self.calls[("transactions", account_id)] += 1
        if account_id == self.failure_account:
            raise PluggyError("provider_error", "Temporary provider failure.", True, {"account_id": account_id})
        return self.page(self.transactions.get(account_id, []), "cursor")

    def list_bills(self, account_id, stop_after=None):
        self.calls[("bills", account_id)] += 1
        rows = self.bills if account_id == "account-card" else []
        return self.page(rows)

    def list_investments(self, item_id, stop_after=None):
        self.calls[("investments", item_id)] += 1
        return self.page([row for row in self.investments if row["itemId"] == item_id])

    def get_investment(self, investment_id):
        self.calls[("investment", investment_id)] += 1
        return deepcopy(next(row for row in self.investments if row["id"] == investment_id))

    def list_investment_transactions(self, investment_id, stop_after=None):
        self.calls[("investment-transactions", investment_id)] += 1
        return self.page(self.movements)


@pytest.fixture
def config():
    return Config("client", "secret", ("item-bank", "item-invest"), max_workers=4)


@pytest.fixture
def fake(fixture_json):
    return FakeClient(fixture_json=fixture_json)


def parse(*arguments):
    return cli.build_parser().parse_args(list(arguments))


@pytest.mark.parametrize(
    "arguments,expected_key",
    [
        (("doctor",), "item_id"),
        (("accounts",), "account_id"),
        (("transactions", "--date-from", "2026-09-01", "--date-to", "2026-09-09"), "transaction_id"),
        (("bills",), "bill_id"),
        (("investments",), "investment_id"),
        (("investment-transactions", "--date-from", "2026-09-01", "--date-to", "2026-09-09"), "investment_transaction_id"),
        (("activity", "--date-from", "2026-09-01", "--date-to", "2026-09-09"), "source_kind"),
    ],
)
def test_every_command_returns_stable_success_envelope(arguments, expected_key, config, fake):
    document = cli.execute(parse(*arguments), config, fake)
    assert list(document) == ["status", "items", "meta", "failures"]
    assert document["status"] == "success"
    assert document["items"]
    assert expected_key in document["items"][0]
    assert document["meta"]["count"] == len(document["items"])


def test_account_filters_and_item_scope(config, fake):
    document = cli.execute(
        parse("accounts", "--item-id", "item-bank", "--account-type", "credit"), config, fake
    )
    assert [row["account_id"] for row in document["items"]] == ["account-card"]
    assert document["meta"]["filters"]["account_type"] == "credit"


def test_transaction_filters_preserve_provider_direction_and_card_metadata(config, fake):
    document = cli.execute(
        parse(
            "transactions", "--account-type", "credit", "--status", "pending",
            "--direction", "debit", "--description", "coffee", "--min-amount", "10",
            "--max-amount", "20", "--date-from", "2026-09-01", "--date-to", "2026-09-09",
        ),
        config, fake,
    )
    assert len(document["items"]) == 1
    row = document["items"][0]
    assert row["amount"] == 18.5
    assert row["direction"] == "DEBIT"
    assert row["credit_card_metadata"]["installmentNumber"] == 1


def test_investment_type_and_movement_date_filters(config, fake):
    positions = cli.execute(parse("investments", "--investment-type", "mutual_fund"), config, fake)
    assert [row["investment_id"] for row in positions["items"]] == ["investment-fund"]
    movements = cli.execute(
        parse(
            "investment-transactions", "--movement-type", "buy",
            "--date-from", "2026-09-01", "--date-to", "2026-09-09",
        ), config, fake,
    )
    assert [row["investment_transaction_id"] for row in movements["items"]] == ["movement-buy"]
    assert fake.calls[("investment-transactions", "investment-fund")] == 1


def test_raw_mode_keeps_normalized_record_and_redacts_secret_fields(config, fake):
    fake.accounts[0]["apiKey"] = "must-not-leak"
    document = cli.execute(parse("accounts", "--limit", "1", "--raw"), config, fake)
    assert document["items"][0]["account_id"] == "account-bank"
    assert document["items"][0]["raw"]["apiKey"] == "[REDACTED]"


def test_empty_bill_result_is_success_and_is_not_synthesized(config, fake):
    fake.bills = []
    document = cli.execute(parse("bills"), config, fake)
    assert document["status"] == "success"
    assert document["items"] == []
    assert document["failures"] == []


def test_explicit_bill_account_must_be_credit(config, fake):
    with pytest.raises(cli.ValidationError, match="credit account"):
        cli.execute(parse("bills", "--account-id", "account-bank"), config, fake)


def test_default_and_custom_output_limits_report_truncation(config, fake):
    fake.accounts = [fake.accounts[0]]
    fake.transactions["account-bank"] = [
        {
            "id": f"transaction-{index}", "accountId": "account-bank",
            "date": f"2026-09-{(index % 9) + 1:02d}T10:00:00Z", "description": "Test",
            "amount": index, "type": "CREDIT", "status": "POSTED",
        }
        for index in range(120)
    ]
    default = cli.execute(parse("transactions"), config, fake)
    custom = cli.execute(parse("transactions", "--limit", "25"), config, fake)
    assert len(default["items"]) == 100
    assert default["meta"]["truncated"] is True
    assert len(custom["items"]) == 25
    assert custom["meta"]["truncated"] is True


def test_activity_is_descending_and_reuses_discovery(config, fake):
    document = cli.execute(
        parse("activity", "--date-from", "2026-09-01", "--date-to", "2026-09-09"),
        config, fake,
    )
    dates = [row.get("date") or row.get("trade_date") for row in document["items"]]
    assert dates == sorted(dates, reverse=True)
    assert {row["source_kind"] for row in document["items"]} == {
        "bank_transaction", "credit_transaction", "investment_movement"
    }
    assert fake.calls[("accounts", "item-bank")] == 1
    assert fake.calls[("investments", "item-invest")] == 1
    assert all(count == 1 for (kind, _), count in fake.calls.items() if kind == "item")
    assert document["meta"]["pagination"] == []
    assert document["meta"]["pagination_summary"] == {
        "resources_read": 7,
        "pages_read": 7,
        "multi_page_resources": 0,
        "truncated_resources": 0,
        "by_kind": {"cursor": 2, "page": 5},
        "by_source_kind": {
            "account_discovery": 2,
            "account_transaction": 2,
            "investment_discovery": 2,
            "investment_movement": 1,
        },
    }


def test_partial_failure_keeps_successful_account_results(config, fake):
    fake.failure_account = "account-card"
    document = cli.execute(
        parse("transactions", "--date-from", "2026-09-01", "--date-to", "2026-09-09"),
        config, fake,
    )
    assert document["status"] == "partial"
    assert [row["transaction_id"] for row in document["items"]] == ["transaction-income"]
    assert document["failures"][0]["resource"] == {"account_id": "account-card"}


def test_successful_empty_resource_plus_failure_is_partial(config, fake):
    fake.transactions["account-bank"] = []
    fake.failure_account = "account-card"
    document = cli.execute(
        parse("transactions", "--date-from", "2026-09-01", "--date-to", "2026-09-09"),
        config, fake,
    )
    assert document["items"] == []
    assert document["status"] == "partial"


def test_complete_failure_is_error_and_nonzero_exit(monkeypatch, fixture_json, capsys):
    FakeClient.fixture_data = fixture_json
    FakeClient.failure_account = None
    monkeypatch.setattr(cli, "PluggyClient", FakeClient)
    exit_code = cli.main(["doctor"], environment={})
    output = capsys.readouterr().out
    assert exit_code == 1
    assert '"status":"error"' in output


def test_successful_main_writes_json_and_returns_zero(monkeypatch, fixture_json, capsys):
    FakeClient.fixture_data = fixture_json
    FakeClient.failure_account = None
    monkeypatch.setattr(cli, "PluggyClient", FakeClient)
    environment = {
        "PLUGGY_CLIENT_ID": "client", "PLUGGY_CLIENT_SECRET": "secret",
        "PLUGGY_ITEM_IDS": "item-bank,item-invest",
    }
    exit_code = cli.main(["accounts", "--account-type", "credit"], environment=environment)
    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"status":"success"' in output
    assert "account-card" in output
    assert "secret" not in output


def test_invalid_dates_amounts_scope_and_limits_are_rejected(config, fake):
    with pytest.raises(cli.ValidationError, match="date-from"):
        cli.execute(parse("transactions", "--date-from", "2026-09-09", "--date-to", "2026-09-01"), config, fake)
    with pytest.raises(cli.ValidationError, match="min-amount"):
        cli.execute(parse("transactions", "--min-amount", "20", "--max-amount", "10"), config, fake)
    with pytest.raises(cli.ValidationError, match="narrow"):
        cli.execute(parse("accounts", "--item-id", "not-configured"), config, fake)
    with pytest.raises(SystemExit):
        parse("accounts", "--limit", "501")


def test_fanout_never_exceeds_four_workers(config, fake):
    runner = cli.CommandRunner(config, fake)
    lock = threading.Lock()
    active = 0
    maximum = 0

    def work():
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.01)
        with lock:
            active -= 1
        return True

    results = runner._run_parallel([({"job": index}, work) for index in range(8)])
    assert all(result is True for _, result in results)
    assert 1 < maximum <= 4


def test_freshness_uses_provider_timestamp_not_request_time(config, fake):
    document = cli.execute(parse("doctor"), config, fake)
    values = {entry["source_updated_at"] for entry in document["meta"]["freshness"]}
    assert values == {"2026-09-08T12:00:00Z", "2026-09-08T13:00:00Z"}
    assert "retrieved_at" not in document["meta"]
