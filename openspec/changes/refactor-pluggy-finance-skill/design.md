## Context

The existing skill exposes financial data through a large instruction file and an import-driven Python provider layer. That design makes agents discover implementation details before they can perform a query, duplicates responsibilities across modules, and contains behavior that no longer matches Pluggy's current REST contracts. The refactor must support bank accounts, credit cards, bills, investments, and their transactions while keeping agent context and API usage bounded.

Pluggy resources are connected through Items. Accounts and investments are then discovered from each configured Item, while transactions and bills require the corresponding account or investment identifier. A single user request can therefore require discovery followed by bounded fan-out across several resources. The implementation must preserve partial results when one Item or resource fails.

The skill is maintained for agent consumption. All maintained instructions, code, command names, options, schemas, messages, references, fixtures, and tests must be in English even when a user interacts with the agent in another language.

## Goals / Non-Goals

**Goals:**

- Provide a small, deterministic `pluggy-finance` command surface that an agent can invoke without importing Python modules.
- Query Pluggy directly through one reusable HTTP client with correct authentication, pagination, retry, and error behavior.
- Cover connection diagnostics, accounts, bank and credit-card transactions, bills, investments, investment transactions, and unified activity.
- Return stable, bounded JSON that preserves important provider semantics and exposes partial failures.
- Keep credentials out of command arguments, output, logs, fixtures, and exceptions.
- Make the main `SKILL.md` concise and route uncommon setup or troubleshooting details to references.
- Remove unnecessary abstractions, dependencies, persistence, and cache behavior.

**Non-Goals:**

- Creating an MCP server or distributable Codex plugin in this change.
- Creating, updating, deleting, categorizing, or synchronizing Pluggy resources.
- Implementing Pluggy Connect or dashboard onboarding flows.
- Supporting financial providers other than Pluggy.
- Persisting transactions locally or providing portfolio, tax, budgeting, or accounting analytics.
- Synthesizing a credit-card bill when Pluggy does not return one.

## Decisions

### 1. Use a CLI as the agent-facing contract

The package will expose a `pluggy-finance` entry point with these commands:

- `doctor`
- `accounts`
- `transactions`
- `bills`
- `investments`
- `investment-transactions`
- `activity`

The CLI is the only public execution contract documented by the skill. Python modules remain internal implementation details. This avoids requiring the agent to construct scripts or understand class hierarchies for routine queries.

The alternative was to preserve `FinancialToolsProvider` as the public API. It was rejected because it increases instruction size, couples the skill to Python imports, and makes stable serialization and error handling harder to enforce. A native MCP server remains a possible later layer over the same client and schemas, but is intentionally outside this refactor.

### 2. Use one direct REST client and one HTTP dependency

`scripts/pluggy_client.py` will own authentication, HTTP requests, retries, pagination, and response validation. `scripts/cli.py` will own argument parsing, resource discovery, filtering, aggregation, and serialization. Small schema or error modules may be retained only when they remove duplication.

The implementation will use `requests` as its only external HTTP dependency and remove `pluggy-sdk`. Using both the SDK and direct HTTP was rejected because it produces two authentication paths and inconsistent endpoint behavior. A standard-library-only client was considered, but `requests` provides clearer timeout, session, and test-adapter behavior with little additional surface area.

### 3. Load credentials and Item scope from the environment

The client reads `PLUGGY_CLIENT_ID` and `PLUGGY_CLIENT_SECRET` from the environment. Configured Items are read from comma-separated `PLUGGY_ITEM_IDS`; `PLUGGY_ITEM_ID` remains a temporary single-Item compatibility fallback during migration. Explicit CLI identifier filters can narrow the configured scope but cannot introduce mutation behavior.

Secrets will not be accepted as CLI flags. Authentication headers and request bodies are redacted before an error or diagnostic object is serialized.

### 4. Enforce a stable JSON envelope

Every command returns one JSON object with this shape:

```json
{
  "status": "success",
  "items": [],
  "meta": {
    "count": 0,
    "truncated": false,
    "filters": {},
    "freshness": []
  },
  "failures": []
}
```

`status` is `success`, `partial`, or `error`. `items` contains normalized records. `meta` describes applied filters, returned counts, truncation, pagination, and source freshness. `failures` contains stable error codes and resource context without credentials or full provider payloads.

Normalized output is the default. `--raw` may add the corresponding provider object under a `raw` field but does not replace the envelope or disable secret redaction. This preserves inspectability without making large provider payloads the routine path.

### 5. Bound default queries and output

Transaction-oriented commands default to the most recent 30 days when no date range is supplied. The default output limit is 100 records and the maximum accepted output limit is 500 records. Commands expose explicit date, Item, account, investment, type, status, and direction filters where the underlying resource supports them.

The implementation may fetch more provider records than the requested output limit when local filtering is required, but it uses a documented page and record safety cap. Reaching a safety cap produces `meta.truncated: true` and pagination metadata instead of silently claiming completeness.

These defaults reduce agent context usage and accidental high-cost fan-out. Users can request a wider period or larger result set explicitly.

### 6. Implement pagination per endpoint family

The v2 transaction client follows Pluggy's continuation cursor until the requested result limit, provider exhaustion, or the safety cap. The v1 clients follow `page`, `pageSize`, and `totalPages` semantics. Continuations are tracked so a repeated cursor or page cannot create an infinite loop.

Investment transaction date filtering occurs locally when Pluggy does not provide equivalent server-side filters. Pagination must happen before the client declares a locally filtered result complete.

Pagination helpers remain endpoint-aware rather than forcing cursor and page pagination into one generic abstraction. This small duplication is preferable to obscuring different API contracts.

### 7. Discover resources once and fan out with bounded concurrency

Each command builds a request-scoped inventory of configured Items, accounts, and investments and reuses it for subsequent calls. Independent resource requests run with at most four workers. The command stops scheduling unnecessary pages after its output limit is satisfied.

Failures are isolated by Item and resource. Successful records are returned with `status: partial` when another resource fails. A total failure returns `status: error` and a non-zero process exit code. This is more useful to an agent than either swallowing failures or discarding all successful results.

### 8. Preserve financial meaning and provider freshness

Normalized transactions retain the signed amount, provider-supplied direction or type, status, account type and subtype, credit-card metadata when available, and identifiers needed to trace the source. Investment movements retain the provider movement type and investment identifier. The client will not infer direction solely from the sign when Pluggy supplies an explicit value.

Freshness fields come from Item or resource timestamps returned by Pluggy. The current request time may be recorded separately as `retrieved_at`, but it must not be presented as source freshness.

### 9. Restrict the client to read-only financial access

The request layer will allow only the authentication call and an explicit list of GET routes needed by the commands. No generic arbitrary-path command will be exposed. This keeps the skill read-only by construction and prevents future instructions from accidentally enabling resource mutation.

Retries apply only to safe authentication renewal, transient network failures, rate limiting, and retryable server responses. Authentication is renewed once after an unauthorized response. Timeouts and retry counts are finite and represented in stable failures when exhausted.

### 10. Separate concise routing from detailed references

`SKILL.md` will describe when to use the skill, the command-selection table, essential safety rules, and a few canonical examples. Setup, environment variables, output schemas, endpoint behavior, and troubleshooting move to focused files under `references/` and are loaded only when relevant.

`README.md` remains human-facing project documentation. It may be more detailed than `SKILL.md`, but it must use the same CLI contract and must not document removed imports, caches, or unsupported endpoint behavior.

### 11. Test contracts at the HTTP and CLI boundaries

Tests will use sanitized Pluggy-shaped fixtures and mocked HTTP responses. They will cover authentication renewal, both pagination families, multi-Item and multi-account aggregation, credit-card inclusion, bill behavior, investment movements, local date filtering, bounded output, partial failures, exit codes, raw output, and credential redaction.

CLI tests will validate the JSON envelope and public command behavior. Tests centered only on internal models or caches are insufficient because those components are not the new public contract.

## Risks / Trade-offs

- **Breaking existing Python imports:** Removing `FinancialToolsProvider` can break private consumers. The migration keeps the old modules only until the CLI reaches tested parity, then removes them in the same change with clear release notes and replacement examples.
- **Fan-out latency and rate limits:** Querying several Items or accounts can create many requests. Request-scoped discovery reuse, four-worker concurrency, server-side filters, early stopping, and bounded defaults limit the impact.
- **Provider schema variability:** Institutions may omit or reinterpret optional fields. Normalized fields remain nullable, identifiers and provider values are preserved, and `--raw` supports investigation without changing the normal contract.
- **Large investment histories:** Local date filtering can require extra pages. Safety caps and explicit truncation metadata prevent unbounded requests while making incompleteness visible.
- **Missing open bills:** Some institutions may not return a current bill. The CLI reports no bill and relevant source context instead of synthesizing an amount from transactions.
- **API contract drift:** Pluggy endpoints can evolve. Endpoint-specific client tests, sanitized fixtures, and dated official API references make drift easier to detect and update.

## Migration Plan

1. Add the new direct REST client, stable schemas, CLI entry point, and contract tests alongside the existing implementation.
2. Implement every required command and verify parity for supported read-only queries using mocked Pluggy responses.
3. Rewrite `SKILL.md`, references, and `README.md` in English and switch all examples to `pluggy-finance`.
4. Remove the superseded provider, cache, storage, and model code plus unused dependencies after no maintained documentation or tests import them.
5. Run the complete test suite, package installation check, CLI help check, and an English-content audit before release.

No financial data migration is required because the new design does not persist provider data. Rollback consists of reverting the code and documentation change; Pluggy resources are unaffected because the client is read-only.
