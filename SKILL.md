---
name: open-finance-banking
description: Read Pluggy accounts, card bills, transactions, investments, investment movements, connection health, and unified activity. Use for questions about the user's connected financial data.
category: productivity
---

# Pluggy financial data

Use `pluggy-finance` for read-only questions about financial data already collected by Pluggy. Routine queries require only this file. Load a reference only for setup, schema details, endpoint behavior, or troubleshooting.

## Choose a command

| User intent | Command |
|---|---|
| Check credentials, Item access, or freshness | `pluggy-finance doctor` |
| List bank and credit-card accounts | `pluggy-finance accounts` |
| Search bank or card transactions | `pluggy-finance transactions` |
| List collected credit-card bills | `pluggy-finance bills` |
| List investment positions | `pluggy-finance investments` |
| Search investment movements | `pluggy-finance investment-transactions` |
| Combine bank, card, and investment activity | `pluggy-finance activity` |

Commands write exactly one JSON document to standard output. A `success` or `partial` result is machine-readable with exit code 0; complete failure uses exit code 1.

## Essential options

- Transaction-oriented commands default to the latest 30 calendar days.
- List commands default to 100 results. Use `--limit N` for 1–500 results.
- Use `--date-from YYYY-MM-DD` and `--date-to YYYY-MM-DD` for an explicit period.
- Use `--item-id`, `--account-id`, or `--investment-id` to narrow scope.
- Use `--raw` only when normalized fields are insufficient; authentication material remains redacted.
- Run `<command> --help` for command-specific filters.

## Canonical examples

```bash
pluggy-finance accounts --account-type credit
pluggy-finance transactions --account-type bank --date-from 2026-09-01 --date-to 2026-09-09
pluggy-finance transactions --account-id ACCOUNT_ID --description "coffee" --limit 25
pluggy-finance bills --account-id CREDIT_ACCOUNT_ID
pluggy-finance investments --investment-type MUTUAL_FUND
pluggy-finance investment-transactions --movement-type BUY --date-from 2026-09-01
pluggy-finance activity --limit 100
```

## Safety

- This skill only authenticates and reads allowlisted Pluggy resources.
- Refuse requests to create, update, synchronize, categorize, or delete data, move money, or modify connections.
- Never request credentials in chat, pass them as command flags, or expose them in output.
- Preserve signed amounts, provider direction/type, status, and freshness timestamps; do not infer or rewrite financial meaning.
- Treat `partial` as usable data plus isolated failures. Explain incompleteness when `meta.truncated` is true.
- An empty bill list means Pluggy supplied no bills; never synthesize an open bill.

## References

- Setup or environment errors: [references/setup.md](references/setup.md)
- Response fields: [references/json-schema.md](references/json-schema.md)
- Endpoint or pagination investigation: [references/pluggy-api.md](references/pluggy-api.md) and [references/pagination.md](references/pagination.md)
- Operational failures: [references/troubleshooting.md](references/troubleshooting.md)
