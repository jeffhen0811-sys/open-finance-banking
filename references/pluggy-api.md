# Pluggy read-only endpoint behavior

This implementation uses `https://api.pluggy.ai` and permits only the following routes.

| Purpose | Request |
|---|---|
| Obtain an internal API key | `POST /auth` |
| Diagnose one configured Item | `GET /items/{id}` |
| Discover Item accounts | `GET /accounts?itemId={id}` |
| Resolve one explicit account | `GET /accounts/{id}` |
| Read account transactions | `GET /v2/transactions?accountId={id}` |
| Read collected card bills | `GET /bills?accountId={id}` |
| Discover Item investments | `GET /investments?itemId={id}` |
| Resolve one explicit investment | `GET /investments/{id}` |
| Read investment movements | `GET /investments/{id}/transactions` |

Financial-resource requests are GET-only. Item synchronization, transaction categorization, connection changes, and arbitrary paths are not supported.

## Important semantics

- Accounts use Pluggy's provider `type` and `subtype`; the client does not hard-code institutions.
- v2 transactions preserve their signed `amount`, provider `type`, `status`, category, operation type, and credit-card metadata.
- A positive credit-card transaction may represent a charge while a negative one may represent a payment. Never infer direction over Pluggy's `type`.
- An empty bills response remains empty and is distinct from a failed request.
- Investment movement date filters are applied locally after complete or visibly bounded page traversal.
- Freshness is taken from Pluggy timestamps such as `lastSuccessfulUpdateAt` or `updatedAt`.

Official references, verified 2026-09-09:

- [Basic concepts](https://docs.pluggy.ai/docs/basic-concepts)
- [Accounts](https://docs.pluggy.ai/reference/accounts-list)
- [Transactions](https://docs.pluggy.ai/reference/transactions-list-by-cursor)
- [Bills](https://docs.pluggy.ai/reference/bills-list)
- [Investment transactions](https://docs.pluggy.ai/reference/investment-transactions-list)
