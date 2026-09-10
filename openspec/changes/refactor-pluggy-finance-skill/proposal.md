## Why

The current skill makes routine financial queries expensive and unreliable for an agent because its instructions are long, its execution path spans several loosely connected abstractions, and its implementation diverges from the current Pluggy API contract. Refactoring now will reduce context usage, API calls, retries, and maintenance while making bank, credit-card, bill, and investment data consistently accessible.

## What Changes

- **BREAKING**: Replace the import-driven `FinancialToolsProvider` workflow with a compact, agent-friendly `pluggy-finance` CLI that returns stable JSON.
- Access the Pluggy REST API directly through one HTTP client, including authentication, token renewal, pagination, retries, and structured errors.
- Provide commands for diagnostics, accounts, account and credit-card transactions, bills, investments, investment transactions, and unified financial activity.
- Resolve configured Items and related resource identifiers automatically for common queries, while retaining explicit identifier filters for precise requests.
- Preserve Pluggy transaction semantics, including signed amounts, provider-supplied direction, status, account type and subtype, credit-card metadata, investment movement type, and source freshness.
- Bound response size by default and support opt-in raw output so agent context is not filled with unnecessary provider payloads.
- Reduce `SKILL.md` to concise routing and command guidance, moving setup and API details into selectively loaded references.
- Remove unused or unjustified provider abstractions, storage code, cache claims, imports, and dependencies.
- Add contract-focused tests for authentication, pagination, resource mapping, multi-account aggregation, partial failures, and secret-safe output.
- Require all maintained content to be in English, including skill instructions, source code, command names, option names, schemas, messages, references, fixtures, and tests.

## Capabilities

### New Capabilities

- `pluggy-financial-data-query`: Read-only, agent-efficient access to Pluggy accounts, transactions, credit cards, bills, investments, investment movements, connection status, and unified activity through a deterministic English-language CLI contract.

### Modified Capabilities

None.

## Impact

- Replaces the public usage documented in `SKILL.md` and `README.md`.
- Refactors or removes the existing modules under `scripts/` and introduces an executable CLI entry point.
- Updates Pluggy endpoint handling and normalized output schemas.
- Changes dependency selection to a single direct HTTP approach.
- Replaces the current shallow unit tests with API-client and CLI contract tests backed by fixtures.
- Does not add any capability that moves money, changes financial data, updates Items, or exposes Pluggy credentials or API keys.
