# Pluggy Finance CLI

`pluggy-finance` is a deterministic, read-only command interface for financial data already collected by Pluggy. It covers connection diagnostics, bank and credit-card accounts, transactions, bills, investments, investment movements, and unified recent activity.

## Install

Python 3.10 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .
```

Configure credentials outside command history and select one or more existing Pluggy Items:

```bash
export PLUGGY_CLIENT_ID="..."
export PLUGGY_CLIENT_SECRET="..."
export PLUGGY_ITEM_IDS="ITEM_ID_1,ITEM_ID_2"
pluggy-finance doctor
```

`PLUGGY_ITEM_ID` remains a temporary fallback for one Item. See [setup](references/setup.md) for all environment settings.

## Commands

```text
doctor                   Validate configuration, authentication, Item access, and freshness
accounts                 List bank and credit-card accounts
transactions             Search account transactions
bills                    List collected credit-card bills
investments              List investment positions
investment-transactions  Search movements for one or all investments
activity                 Merge bank, card, and investment activity chronologically
```

Examples:

```bash
pluggy-finance accounts --account-type all
pluggy-finance transactions --account-type credit --date-from 2026-09-01 --limit 100
pluggy-finance bills
pluggy-finance investments --investment-type MUTUAL_FUND
pluggy-finance activity --date-from 2026-09-01 --date-to 2026-09-09
```

Every command emits one stable JSON envelope with `status`, `items`, `meta`, and `failures`. Normal output is bounded to 100 records; `--limit` accepts at most 500. `--raw` adds a redacted provider object without replacing normalized fields.

## Read-only scope

The HTTP client permits authentication plus GET requests for configured Items, accounts, v2 transactions, bills, investments, and investment transactions. It has no generic path command and rejects financial-resource mutations. It does not synchronize Items, categorize transactions, persist financial records, or synthesize missing bills.

## Migration from 0.1

The Python import contract based on `FinancialToolsProvider`, `pluggy_provider`, models, cache, and storage has been removed. Replace custom imports with the `pluggy-finance` command and consume its JSON output. The `pluggy-sdk` dependency is no longer used; the package now has one direct HTTP dependency, `requests`.

## Pluggy documentation

- [API environment, response evolution, and pagination](https://docs.pluggy.ai/docs/basic-concepts)
- [Accounts list](https://docs.pluggy.ai/reference/accounts-list)
- [Cursor-based v2 transactions](https://docs.pluggy.ai/reference/transactions-list-by-cursor)
- [Credit-card bills list](https://docs.pluggy.ai/reference/bills-list)
- [Investment transactions list](https://docs.pluggy.ai/reference/investment-transactions-list)

The links above were verified against the official Pluggy documentation on 2026-09-09.

## Development

```bash
python -m pip install -e . pytest
pytest
```

Tests use sanitized provider-shaped fixtures and mocked HTTP sessions. No live credentials are required.

## License

MIT
