# Verification

Verified on 2026-09-09 in an isolated Python 3.14 virtual environment.

## Automated tests

- Full suite: `48 passed`.
- Focused mocked end-to-end smoke selection: `11 passed in 0.05s`.
- Covered `accounts`, credit-card `transactions`, `bills`, `investments`, `investment-transactions`, and unified `activity` using sanitized Pluggy-shaped fixtures.
- Covered successful, partial, empty, truncated, and complete-error envelopes.
- Covered compact pagination summaries and preservation of actionable pagination details.

## Package and command interface

- Built and installed `open_finance_banking-0.2.0-py3-none-any.whl` in the isolated environment.
- Verified `pluggy-finance --help` and help for `doctor`, `accounts`, `transactions`, `bills`, `investments`, `investment-transactions`, and `activity`.
- Every help invocation exited with code 0 and displayed English command and option text.

## Maintained-content audit

- No non-English maintained source, test, fixture, instruction, or example text was found.
- No absolute user paths or `sys.path` injection examples were found.
- No maintained source imports the removed provider, cache, storage, tool, or model modules.
- The only maintained mentions of `FinancialToolsProvider`, `pluggy_provider`, and `pluggy-sdk` are explicit migration notes explaining their removal.
- No credential value was found. The credential-pattern audit matched only the expected environment-variable loader.
- Documentation contains no cache, persistence, provider-import, mutation, or unsupported endpoint claim presented as current behavior.

## Official endpoint review

Official Pluggy documentation links for accounts, v2 cursor transactions, bills, investment transactions, and pagination were checked on 2026-09-09. The maintained reference uses `GET /investments/{id}/transactions` for investment movements and treats the v2 `next` value as a query containing the `after` cursor.
