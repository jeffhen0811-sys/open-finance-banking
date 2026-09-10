## 1. Package and CLI Foundation

- [x] 1.1 Update `pyproject.toml` to remove `pluggy-sdk`, retain a single direct HTTP dependency, and register the `pluggy-finance` console entry point.
- [x] 1.2 Implement English-language configuration loading for credentials, `PLUGGY_ITEM_IDS`, the temporary `PLUGGY_ITEM_ID` fallback, timeouts, retry limits, and pagination safety caps.
- [x] 1.3 Implement the stable `success`, `partial`, and `error` JSON envelope with structured metadata, failures, and deterministic serialization.
- [x] 1.4 Add the `doctor`, `accounts`, `transactions`, `bills`, `investments`, `investment-transactions`, and `activity` command parsers with English help and validated shared options.

## 2. Direct Pluggy REST Client

- [x] 2.1 Implement `scripts/pluggy_client.py` with a reusable HTTP session, finite timeouts, and an explicit read-only endpoint allowlist.
- [x] 2.2 Implement Pluggy authentication, in-process API-key reuse, one-time renewal after an unauthorized response, and credential redaction.
- [x] 2.3 Implement stable error classification for configuration, authentication, validation, rate limiting, network, provider, pagination, and unexpected-response failures.
- [x] 2.4 Implement bounded retries for safe transient failures and preserve retryability and resource context in structured failures.
- [x] 2.5 Implement v2 transaction cursor pagination, including `next` query handling, repeated-continuation detection, early stopping, and visible truncation.
- [x] 2.6 Implement v1 page pagination for accounts, bills, investments, and investment movements, including total-page traversal and safety-boundary metadata.

## 3. Discovery and Normalization

- [x] 3.1 Implement request-scoped Item discovery and diagnostics with accessibility, connector context, and provider-supplied freshness timestamps.
- [x] 3.2 Implement account discovery and normalization for bank and credit-card accounts without hard-coded institution values.
- [x] 3.3 Implement account transaction normalization that preserves signed amount, provider direction or type, status, category, account context, and credit-card metadata.
- [x] 3.4 Implement credit-card bill normalization and represent an empty provider result without synthesizing an open bill.
- [x] 3.5 Implement investment position normalization with provider identifiers, types, balances, profit, withdrawal amount, status, and relevant dates.
- [x] 3.6 Implement investment movement normalization with provider movement type, investment context, and local date filtering after complete or visibly bounded pagination.
- [x] 3.7 Implement raw-field inclusion behind `--raw` while preserving the normalized envelope and redacting authentication material.

## 4. Query Commands and Execution Efficiency

- [x] 4.1 Implement `doctor` so it validates configuration, authentication, Item access, and freshness without returning financial transaction payloads.
- [x] 4.2 Implement `accounts` with Item and bank-or-credit type filters.
- [x] 4.3 Implement `transactions` for one account or all matching bank and credit accounts with date, status, direction, description, and amount filters.
- [x] 4.4 Implement `bills` for one credit-card account or all discovered credit-card accounts.
- [x] 4.5 Implement `investments` for one or all configured Items with provider investment-type filtering.
- [x] 4.6 Implement `investment-transactions` for one investment or all discovered investments with date and movement-type filtering.
- [x] 4.7 Implement `activity` by combining bank transactions, credit-card transactions, and investment movements with explicit source kinds and descending chronological order.
- [x] 4.8 Reuse discovery results within each invocation and implement per-resource fan-out with a maximum of four workers and isolated partial failures.
- [x] 4.9 Enforce the 30-day default period, 100-record default output, 500-record maximum output, early stopping, and accurate truncation metadata across applicable commands.
- [x] 4.10 Return a non-zero exit code for complete failure while keeping successful and partial responses machine-readable on standard output.

## 5. Skill and Documentation Refactor

- [x] 5.1 Rewrite `SKILL.md` in concise English with activation guidance, a command-selection table, safety rules, and canonical examples sufficient for routine queries.
- [x] 5.2 Create or update focused English references for installation, environment configuration, JSON schemas, endpoint behavior, pagination, and troubleshooting.
- [x] 5.3 Rewrite `README.md` in English around the `pluggy-finance` contract, migration guidance, supported read-only scope, and verified official Pluggy documentation links.
- [x] 5.4 Remove stale cache, persistence, provider-import, absolute-path, unsupported endpoint, and unverified capability claims from maintained instructions and examples.

## 6. Legacy Removal

- [x] 6.1 Identify any maintained imports of `FinancialToolsProvider`, `pluggy_provider`, cache, storage, and superseded model interfaces after CLI parity is complete.
- [x] 6.2 Remove obsolete provider, cache, storage, model, and tool modules that are no longer required by the direct client and CLI.
- [x] 6.3 Remove unused dependencies and update package exports so only supported internal modules and the public CLI remain installable.

## 7. Contract Tests

- [x] 7.1 Add sanitized Pluggy-shaped fixtures for Items, bank accounts, credit cards, transactions, bills, investments, investment movements, pagination, and provider failures.
- [x] 7.2 Add HTTP-client tests for authentication reuse and renewal, timeouts, retry boundaries, read-only route enforcement, and secret-safe errors.
- [x] 7.3 Add pagination tests for v2 cursors, v1 pages, repeated continuations, safety caps, and local investment-movement filtering.
- [x] 7.4 Add CLI tests for every command, supported filters, default limits, custom limits, raw output, exit codes, and the stable JSON envelope.
- [x] 7.5 Add multi-Item and multi-resource tests for discovery reuse, bank and credit aggregation, bounded concurrency, chronological activity, and partial failures.
- [x] 7.6 Add regression tests proving that missing bills are not synthesized, transaction direction is not inferred over provider values, and request time is not reported as source freshness.

## 8. Verification

- [x] 8.1 Run the complete automated test suite and resolve all failures.
- [x] 8.2 Install the package in an isolated environment and verify the console entry point and English help for every command.
- [x] 8.3 Audit maintained skill files for non-English content, leaked credential patterns, removed import examples, obsolete paths, and unsupported Pluggy operations.
- [x] 8.4 Perform mocked end-to-end smoke queries for accounts, credit-card transactions, bills, investments, investment movements, and unified activity, then record the verification results in the change notes or pull request.
