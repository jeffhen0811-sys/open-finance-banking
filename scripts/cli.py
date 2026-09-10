"""Agent-facing command line interface for read-only Pluggy financial data."""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Callable, Iterable, Mapping, Sequence

from .config import Config
from .envelope import dumps, failure_from_exception, make_envelope
from .errors import PluggyError, ValidationError, redact
from .pluggy_client import PageResult, PluggyClient


DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def _limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if not 1 <= parsed <= MAX_LIMIT:
        raise argparse.ArgumentTypeError(f"limit must be between 1 and {MAX_LIMIT}")
    return parsed


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from exc


def _add_scope(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--item-id", action="append", dest="item_ids",
        help="Narrow the query to a configured Item. Repeat for multiple Items.",
    )


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=_limit, default=DEFAULT_LIMIT, help="Output records (1-500).")
    parser.add_argument("--raw", action="store_true", help="Include redacted provider fields.")


def _add_dates(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--date-from", type=_iso_date, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", type=_iso_date, help="Inclusive end date (YYYY-MM-DD).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pluggy-finance",
        description="Read Pluggy financial data through a stable JSON command interface.",
        epilog="Example: pluggy-finance transactions --account-type credit --date-from 2026-01-01",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="Validate configuration, access, and freshness.")
    _add_scope(doctor)

    accounts = commands.add_parser("accounts", help="List bank and credit-card accounts.")
    _add_scope(accounts)
    _add_output(accounts)
    accounts.add_argument("--account-type", choices=("all", "bank", "credit"), default="all")

    transactions = commands.add_parser("transactions", help="Search bank or credit-card transactions.")
    _add_scope(transactions)
    _add_output(transactions)
    _add_dates(transactions)
    transactions.add_argument("--account-id", help="Query one account instead of discovering accounts.")
    transactions.add_argument("--account-type", choices=("all", "bank", "credit"), default="all")
    transactions.add_argument("--status", help="Match the provider transaction status.")
    transactions.add_argument("--direction", help="Match the provider transaction type or direction.")
    transactions.add_argument("--description", help="Case-insensitive description substring.")
    transactions.add_argument("--min-amount", type=float, help="Minimum signed amount.")
    transactions.add_argument("--max-amount", type=float, help="Maximum signed amount.")

    bills = commands.add_parser("bills", help="List collected credit-card bills.")
    _add_scope(bills)
    _add_output(bills)
    bills.add_argument("--account-id", help="Query one credit-card account.")

    investments = commands.add_parser("investments", help="List investment positions.")
    _add_scope(investments)
    _add_output(investments)
    investments.add_argument("--investment-type", help="Match the provider investment type.")

    movements = commands.add_parser(
        "investment-transactions", help="Search transactions for one or all investments."
    )
    _add_scope(movements)
    _add_output(movements)
    _add_dates(movements)
    movements.add_argument("--investment-id", help="Query one investment position.")
    movements.add_argument("--movement-type", help="Match the provider movement type.")

    activity = commands.add_parser(
        "activity", help="Combine bank, credit-card, and investment activity."
    )
    _add_scope(activity)
    _add_output(activity)
    _add_dates(activity)
    return parser


def _field(payload: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    return None


def _nested(payload: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = payload.get(name)
    return value if isinstance(value, Mapping) else {}


def _raw(record: dict[str, Any], provider: Mapping[str, Any], enabled: bool) -> dict[str, Any]:
    if enabled:
        record["raw"] = redact(dict(provider))
    return record


def normalize_item(item: Mapping[str, Any], raw: bool = False) -> dict[str, Any]:
    connector = _nested(item, "connector")
    record = {
        "item_id": _field(item, "id"),
        "status": _field(item, "status"),
        "error": _field(item, "error"),
        "connector": {
            "id": _field(connector, "id"),
            "name": _field(connector, "name", "institutionName"),
        },
        "source_updated_at": _field(
            item, "lastSuccessfulUpdateAt", "updatedAt", "lastUpdatedAt", "createdAt"
        ),
    }
    return _raw(record, item, raw)


def normalize_account(
    account: Mapping[str, Any], item: Mapping[str, Any] | None, raw: bool
) -> dict[str, Any]:
    credit = _nested(account, "creditData")
    bank = _nested(account, "bankData")
    connector = _nested(item or {}, "connector")
    record = {
        "item_id": _field(account, "itemId") or _field(item or {}, "id"),
        "account_id": _field(account, "id"),
        "type": _field(account, "type"),
        "subtype": _field(account, "subtype", "subType"),
        "institution": _field(account, "institution", "institutionName")
        or _field(connector, "name", "institutionName"),
        "name": _field(account, "name", "marketingName"),
        "number": _field(account, "number"),
        "currency": _field(account, "currencyCode", "currency"),
        "balance": _field(account, "balance"),
        "available_balance": _field(account, "availableBalance")
        or _field(bank, "availableBalance"),
        "credit_limit": _field(credit, "creditLimit", "limit"),
        "available_credit_limit": _field(credit, "availableCreditLimit", "availableLimit"),
        "source_updated_at": _field(account, "updatedAt", "collectedAt"),
    }
    return _raw(record, account, raw)


def normalize_transaction(
    transaction: Mapping[str, Any], account: Mapping[str, Any], raw: bool
) -> dict[str, Any]:
    metadata = _nested(transaction, "creditCardMetadata")
    record = {
        "transaction_id": _field(transaction, "id"),
        "provider_id": _field(transaction, "providerId"),
        "item_id": _field(account, "itemId"),
        "account_id": _field(transaction, "accountId") or _field(account, "id"),
        "account_type": _field(account, "type"),
        "account_subtype": _field(account, "subtype", "subType"),
        "date": _field(transaction, "date"),
        "description": _field(transaction, "description"),
        "amount": _field(transaction, "amount"),
        "currency": _field(transaction, "currencyCode", "currency"),
        "direction": _field(transaction, "type", "direction"),
        "status": _field(transaction, "status"),
        "category": _field(transaction, "category"),
        "operation_type": _field(transaction, "operationType"),
        "credit_card_metadata": dict(metadata) if metadata else None,
        "source_updated_at": _field(transaction, "updatedAt", "collectedAt"),
    }
    return _raw(record, transaction, raw)


def normalize_bill(bill: Mapping[str, Any], account: Mapping[str, Any], raw: bool) -> dict[str, Any]:
    record = {
        "bill_id": _field(bill, "id"),
        "item_id": _field(account, "itemId"),
        "account_id": _field(bill, "accountId") or _field(account, "id"),
        "due_date": _field(bill, "dueDate"),
        "close_date": _field(bill, "closeDate", "closingDate"),
        "total_amount": _field(bill, "totalAmount", "total"),
        "minimum_payment_amount": _field(bill, "minimumPaymentAmount", "minimumPayment"),
        "paid_amount": _field(bill, "paidAmount", "paid"),
        "status": _field(bill, "status"),
        "currency": _field(bill, "currencyCode", "currency")
        or _field(account, "currencyCode", "currency"),
        "source_updated_at": _field(bill, "updatedAt", "collectedAt"),
    }
    return _raw(record, bill, raw)


def normalize_investment(
    investment: Mapping[str, Any], item: Mapping[str, Any] | None, raw: bool
) -> dict[str, Any]:
    connector = _nested(item or {}, "connector")
    record = {
        "item_id": _field(investment, "itemId") or _field(item or {}, "id"),
        "investment_id": _field(investment, "id"),
        "provider_id": _field(investment, "providerId"),
        "institution": _field(investment, "institution", "institutionName")
        or _field(connector, "name", "institutionName"),
        "type": _field(investment, "type"),
        "subtype": _field(investment, "subtype", "subType"),
        "name": _field(investment, "name"),
        "currency": _field(investment, "currencyCode", "currency"),
        "balance": _field(investment, "balance", "currentBalance"),
        "invested_amount": _field(investment, "amount", "investedAmount", "originalAmount"),
        "profit": _field(investment, "profit"),
        "withdrawal_amount": _field(investment, "withdrawalAmount"),
        "status": _field(investment, "status"),
        "date": _field(investment, "date", "issueDate"),
        "due_date": _field(investment, "dueDate", "maturityDate"),
        "source_updated_at": _field(investment, "updatedAt", "collectedAt"),
    }
    return _raw(record, investment, raw)


def normalize_investment_transaction(
    movement: Mapping[str, Any], investment: Mapping[str, Any], raw: bool
) -> dict[str, Any]:
    record = {
        "investment_transaction_id": _field(movement, "id"),
        "item_id": _field(investment, "itemId"),
        "investment_id": _field(movement, "investmentId") or _field(investment, "id"),
        "investment_type": _field(investment, "type"),
        "investment_name": _field(investment, "name"),
        "type": _field(movement, "type"),
        "date": _field(movement, "date"),
        "trade_date": _field(movement, "tradeDate"),
        "description": _field(movement, "description"),
        "amount": _field(movement, "amount"),
        "net_amount": _field(movement, "netAmount"),
        "quantity": _field(movement, "quantity"),
        "value": _field(movement, "value"),
        "source_updated_at": _field(movement, "updatedAt", "collectedAt"),
    }
    return _raw(record, movement, raw)


class CommandRunner:
    def __init__(self, config: Config, client: PluggyClient) -> None:
        self.config = config
        self.client = client
        self._items: dict[str, dict[str, Any]] | None = None
        self._accounts: dict[str, list[dict[str, Any]]] = {}
        self._investments: dict[str, list[dict[str, Any]]] = {}
        self.failures: list[dict[str, Any]] = []
        self.pagination: list[dict[str, Any]] = []
        self.truncated = False

    def _run_parallel(
        self, jobs: Sequence[tuple[dict[str, Any], Callable[[], Any]]]
    ) -> list[tuple[dict[str, Any], Any | None]]:
        if not jobs:
            return []
        with ThreadPoolExecutor(max_workers=min(self.config.max_workers, 4, len(jobs))) as pool:
            futures = [(context, pool.submit(call)) for context, call in jobs]
            results: list[tuple[dict[str, Any], Any | None]] = []
            for context, future in futures:
                try:
                    results.append((context, future.result()))
                except Exception as exc:
                    self.failures.append(failure_from_exception(exc, **context))
                    results.append((context, None))
            return results

    def _scope(self, requested: Iterable[str] | None) -> tuple[str, ...]:
        if not requested:
            return self.config.item_ids
        values = tuple(dict.fromkeys(requested))
        unknown = sorted(set(values) - set(self.config.item_ids))
        if unknown:
            raise ValidationError(
                "--item-id can only narrow PLUGGY_ITEM_IDS.", details={"unknown_item_ids": unknown}
            )
        return values

    def load_items(self, scope: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        if self._items is None:
            self._items = {}
            jobs = [({"item_id": item_id}, lambda item_id=item_id: self.client.get_item(item_id)) for item_id in self.config.item_ids]
            for context, result in self._run_parallel(jobs):
                if result is not None:
                    self._items[context["item_id"]] = result
        return {item_id: self._items[item_id] for item_id in scope if item_id in self._items}

    def load_accounts(
        self, scope: tuple[str, ...], items: Mapping[str, dict[str, Any]]
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        missing = [item_id for item_id in scope if item_id in items and item_id not in self._accounts]
        jobs = [({"item_id": item_id}, lambda item_id=item_id: self.client.list_accounts(item_id)) for item_id in missing]
        for context, result in self._run_parallel(jobs):
            if isinstance(result, PageResult):
                self._accounts[context["item_id"]] = result.records
                self._track_page(result, {**context, "source_kind": "account_discovery"})
        return [
            (account, items[item_id])
            for item_id in scope if item_id in items
            for account in self._accounts.get(item_id, [])
        ]

    def load_investments(
        self, scope: tuple[str, ...], items: Mapping[str, dict[str, Any]]
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        missing = [item_id for item_id in scope if item_id in items and item_id not in self._investments]
        jobs = [({"item_id": item_id}, lambda item_id=item_id: self.client.list_investments(item_id)) for item_id in missing]
        for context, result in self._run_parallel(jobs):
            if isinstance(result, PageResult):
                self._investments[context["item_id"]] = result.records
                self._track_page(result, {**context, "source_kind": "investment_discovery"})
        return [
            (investment, items[item_id])
            for item_id in scope if item_id in items
            for investment in self._investments.get(item_id, [])
        ]

    def _track_page(self, result: PageResult, context: Mapping[str, Any]) -> None:
        self.truncated = self.truncated or result.truncated
        self.pagination.append({**context, **result.metadata})

    @staticmethod
    def _freshness(items: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "item_id": item_id,
                "source_updated_at": _field(
                    item, "lastSuccessfulUpdateAt", "updatedAt", "lastUpdatedAt", "createdAt"
                ),
            }
            for item_id, item in items.items()
        ]

    @staticmethod
    def _account_matches(account: Mapping[str, Any], account_type: str) -> bool:
        return account_type == "all" or str(_field(account, "type") or "").lower() == account_type

    @staticmethod
    def _default_dates(args: argparse.Namespace) -> tuple[str, str]:
        end = args.date_to or date.today().isoformat()
        start = args.date_from or (date.fromisoformat(end) - timedelta(days=29)).isoformat()
        if start > end:
            raise ValidationError("--date-from cannot be later than --date-to.")
        return start, end

    @staticmethod
    def _finish(records: list[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], bool]:
        return records[:limit], len(records) > limit

    def doctor(self, args: argparse.Namespace) -> dict[str, Any]:
        scope = self._scope(args.item_ids)
        items = self.load_items(scope)
        records = [normalize_item(item) for item in items.values()]
        return make_envelope(
            records, self.failures, filters={"item_ids": list(scope)},
            freshness=self._freshness(items), extra_meta={"checks": ["configuration", "authentication", "item_access", "freshness"]},
            successful_resources=len(items),
        )

    def accounts(self, args: argparse.Namespace) -> dict[str, Any]:
        scope = self._scope(args.item_ids)
        items = self.load_items(scope)
        discovered = self.load_accounts(scope, items)
        records = [
            normalize_account(account, item, args.raw)
            for account, item in discovered if self._account_matches(account, args.account_type)
        ]
        records, limited = self._finish(records, args.limit)
        return make_envelope(
            records, self.failures,
            filters={"item_ids": list(scope), "account_type": args.account_type, "limit": args.limit},
            freshness=self._freshness(items), pagination=self.pagination,
            truncated=self.truncated or limited,
            successful_resources=sum(item_id in self._accounts for item_id in scope),
        )

    def _target_accounts(
        self, args: argparse.Namespace, scope: tuple[str, ...], items: Mapping[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if args.account_id:
            try:
                account = self.client.get_account(args.account_id)
            except Exception as exc:
                self.failures.append(failure_from_exception(exc, account_id=args.account_id))
                return []
            item_id = _field(account, "itemId")
            if item_id and item_id not in scope:
                raise ValidationError("The requested account is outside the selected Item scope.")
            return [account] if self._account_matches(account, args.account_type) else []
        return [account for account, _item in self.load_accounts(scope, items) if self._account_matches(account, args.account_type)]

    def transactions(self, args: argparse.Namespace) -> dict[str, Any]:
        if args.min_amount is not None and args.max_amount is not None and args.min_amount > args.max_amount:
            raise ValidationError("--min-amount cannot exceed --max-amount.")
        scope = self._scope(args.item_ids)
        items = self.load_items(scope)
        accounts = self._target_accounts(args, scope, items)
        date_from, date_to = self._default_dates(args)
        can_stop_early = not any(
            value is not None
            for value in (args.status, args.direction, args.description, args.min_amount, args.max_amount)
        )
        jobs = [
            (
                {"account_id": str(_field(account, "id")), "source_kind": "account_transaction"},
                lambda account=account: self.client.paginate_transactions(
                    str(_field(account, "id")),
                    params={"dateFrom": date_from, "dateTo": date_to},
                    stop_after=args.limit if can_stop_early else None,
                ),
            )
            for account in accounts
        ]
        records: list[dict[str, Any]] = []
        successful_reads = 0
        by_id = {str(_field(account, "id")): account for account in accounts}
        for context, result in self._run_parallel(jobs):
            if not isinstance(result, PageResult):
                continue
            successful_reads += 1
            self._track_page(result, context)
            account = by_id[context["account_id"]]
            for transaction in result.records:
                direction = str(_field(transaction, "type", "direction") or "")
                status = str(_field(transaction, "status") or "")
                description = str(_field(transaction, "description") or "")
                amount = _field(transaction, "amount")
                if args.status and status.lower() != args.status.lower():
                    continue
                if args.direction and direction.lower() != args.direction.lower():
                    continue
                if args.description and args.description.lower() not in description.lower():
                    continue
                if args.min_amount is not None and (amount is None or float(amount) < args.min_amount):
                    continue
                if args.max_amount is not None and (amount is None or float(amount) > args.max_amount):
                    continue
                records.append(normalize_transaction(transaction, account, args.raw))
        records.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
        records, limited = self._finish(records, args.limit)
        filters = {
            "item_ids": list(scope), "account_id": args.account_id,
            "account_type": args.account_type, "date_from": date_from, "date_to": date_to,
            "status": args.status, "direction": args.direction, "description": args.description,
            "min_amount": args.min_amount, "max_amount": args.max_amount, "limit": args.limit,
        }
        return make_envelope(
            records, self.failures, filters=filters, freshness=self._freshness(items),
            pagination=self.pagination, truncated=self.truncated or limited,
            successful_resources=successful_reads if jobs else sum(item_id in self._accounts for item_id in scope),
        )

    def bills(self, args: argparse.Namespace) -> dict[str, Any]:
        scope = self._scope(args.item_ids)
        items = self.load_items(scope)
        if args.account_id:
            try:
                account = self.client.get_account(args.account_id)
                if _field(account, "itemId") and _field(account, "itemId") not in scope:
                    raise ValidationError("The requested account is outside the selected Item scope.")
                if not self._account_matches(account, "credit"):
                    raise ValidationError("--account-id for bills must identify a credit account.")
                accounts = [account]
            except Exception as exc:
                if isinstance(exc, ValidationError):
                    raise
                self.failures.append(failure_from_exception(exc, account_id=args.account_id))
                accounts = []
        else:
            accounts = [account for account, _ in self.load_accounts(scope, items) if self._account_matches(account, "credit")]
        jobs = [
            (
                {"account_id": str(_field(account, "id")), "source_kind": "bill"},
                lambda account=account: self.client.list_bills(
                    str(_field(account, "id")), stop_after=args.limit
                ),
            )
            for account in accounts
        ]
        by_id = {str(_field(account, "id")): account for account in accounts}
        records: list[dict[str, Any]] = []
        successful_reads = 0
        for context, result in self._run_parallel(jobs):
            if isinstance(result, PageResult):
                successful_reads += 1
                self._track_page(result, context)
                records.extend(normalize_bill(bill, by_id[context["account_id"]], args.raw) for bill in result.records)
        records.sort(key=lambda row: str(row.get("due_date") or ""), reverse=True)
        records, limited = self._finish(records, args.limit)
        return make_envelope(
            records, self.failures,
            filters={"item_ids": list(scope), "account_id": args.account_id, "limit": args.limit},
            freshness=self._freshness(items), pagination=self.pagination,
            truncated=self.truncated or limited,
            successful_resources=successful_reads if jobs else sum(item_id in self._accounts for item_id in scope),
        )

    def investments(self, args: argparse.Namespace) -> dict[str, Any]:
        scope = self._scope(args.item_ids)
        items = self.load_items(scope)
        discovered = self.load_investments(scope, items)
        records = [
            normalize_investment(investment, item, args.raw)
            for investment, item in discovered
            if not args.investment_type
            or str(_field(investment, "type") or "").lower() == args.investment_type.lower()
        ]
        records, limited = self._finish(records, args.limit)
        return make_envelope(
            records, self.failures,
            filters={"item_ids": list(scope), "investment_type": args.investment_type, "limit": args.limit},
            freshness=self._freshness(items), pagination=self.pagination,
            truncated=self.truncated or limited,
            successful_resources=sum(item_id in self._investments for item_id in scope),
        )

    def _target_investments(
        self, args: argparse.Namespace, scope: tuple[str, ...], items: Mapping[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if args.investment_id:
            try:
                investment = self.client.get_investment(args.investment_id)
            except Exception as exc:
                self.failures.append(failure_from_exception(exc, investment_id=args.investment_id))
                return []
            if _field(investment, "itemId") and _field(investment, "itemId") not in scope:
                raise ValidationError("The requested investment is outside the selected Item scope.")
            return [investment]
        return [investment for investment, _item in self.load_investments(scope, items)]

    def investment_transactions(self, args: argparse.Namespace) -> dict[str, Any]:
        scope = self._scope(args.item_ids)
        items = self.load_items(scope)
        investments = self._target_investments(args, scope, items)
        date_from, date_to = self._default_dates(args)
        jobs = [
            (
                {
                    "investment_id": str(_field(investment, "id")),
                    "source_kind": "investment_movement",
                },
                lambda investment=investment: self.client.list_investment_transactions(str(_field(investment, "id"))),
            )
            for investment in investments
        ]
        by_id = {str(_field(investment, "id")): investment for investment in investments}
        records: list[dict[str, Any]] = []
        successful_reads = 0
        for context, result in self._run_parallel(jobs):
            if not isinstance(result, PageResult):
                continue
            successful_reads += 1
            self._track_page(result, context)
            for movement in result.records:
                movement_date = str(_field(movement, "date", "tradeDate") or "")[:10]
                movement_type = str(_field(movement, "type") or "")
                if movement_date and not date_from <= movement_date <= date_to:
                    continue
                if args.movement_type and movement_type.lower() != args.movement_type.lower():
                    continue
                records.append(normalize_investment_transaction(movement, by_id[context["investment_id"]], args.raw))
        records.sort(key=lambda row: str(row.get("date") or row.get("trade_date") or ""), reverse=True)
        records, limited = self._finish(records, args.limit)
        return make_envelope(
            records, self.failures,
            filters={"item_ids": list(scope), "investment_id": args.investment_id, "date_from": date_from, "date_to": date_to, "movement_type": args.movement_type, "limit": args.limit},
            freshness=self._freshness(items), pagination=self.pagination,
            truncated=self.truncated or limited,
            successful_resources=successful_reads if jobs else sum(item_id in self._investments for item_id in scope),
        )

    def activity(self, args: argparse.Namespace) -> dict[str, Any]:
        scope = self._scope(args.item_ids)
        items = self.load_items(scope)
        accounts = [account for account, _ in self.load_accounts(scope, items)]
        investments = [investment for investment, _ in self.load_investments(scope, items)]
        date_from, date_to = self._default_dates(args)
        jobs: list[tuple[dict[str, Any], Callable[[], PageResult]]] = []
        for account in accounts:
            account_id = str(_field(account, "id"))
            jobs.append((
                {"source_kind": "account_transaction", "account_id": account_id},
                lambda account_id=account_id: self.client.paginate_transactions(
                    account_id, params={"dateFrom": date_from, "dateTo": date_to},
                    stop_after=args.limit,
                ),
            ))
        for investment in investments:
            investment_id = str(_field(investment, "id"))
            jobs.append((
                {"source_kind": "investment_movement", "investment_id": investment_id},
                lambda investment_id=investment_id: self.client.list_investment_transactions(investment_id),
            ))
        accounts_by_id = {str(_field(account, "id")): account for account in accounts}
        investments_by_id = {str(_field(investment, "id")): investment for investment in investments}
        records: list[dict[str, Any]] = []
        successful_reads = 0
        for context, result in self._run_parallel(jobs):
            if not isinstance(result, PageResult):
                continue
            successful_reads += 1
            self._track_page(result, context)
            if context["source_kind"] == "account_transaction":
                account = accounts_by_id[context["account_id"]]
                kind = "credit_transaction" if self._account_matches(account, "credit") else "bank_transaction"
                for transaction in result.records:
                    record = normalize_transaction(transaction, account, args.raw)
                    record["source_kind"] = kind
                    records.append(record)
            else:
                investment = investments_by_id[context["investment_id"]]
                for movement in result.records:
                    movement_date = str(_field(movement, "date", "tradeDate") or "")[:10]
                    if movement_date and date_from <= movement_date <= date_to:
                        record = normalize_investment_transaction(movement, investment, args.raw)
                        record["source_kind"] = "investment_movement"
                        records.append(record)
        records.sort(key=lambda row: str(row.get("date") or row.get("trade_date") or ""), reverse=True)
        records, limited = self._finish(records, args.limit)
        return make_envelope(
            records, self.failures,
            filters={"item_ids": list(scope), "date_from": date_from, "date_to": date_to, "limit": args.limit},
            freshness=self._freshness(items), pagination=self.pagination,
            truncated=self.truncated or limited,
            successful_resources=successful_reads if jobs else (
                sum(item_id in self._accounts for item_id in scope)
                + sum(item_id in self._investments for item_id in scope)
            ),
        )

    def run(self, args: argparse.Namespace) -> dict[str, Any]:
        return getattr(self, args.command.replace("-", "_"))(args)


def execute(args: argparse.Namespace, config: Config, client: PluggyClient | None = None) -> dict[str, Any]:
    return CommandRunner(config, client or PluggyClient(config)).run(args)


def main(argv: Sequence[str] | None = None, environment: Mapping[str, str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = Config.from_env(environment)
        document = execute(args, config)
    except Exception as exc:
        document = make_envelope(failures=[failure_from_exception(exc)])
    sys.stdout.write(dumps(document) + "\n")
    return 1 if document["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
