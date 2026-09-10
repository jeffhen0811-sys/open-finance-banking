# Installation and environment

Use this reference when installing the package or resolving configuration errors.

## Installation

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .
pluggy-finance --help
```

## Required environment variables

| Variable | Meaning |
|---|---|
| `PLUGGY_CLIENT_ID` | Pluggy application client identifier |
| `PLUGGY_CLIENT_SECRET` | Pluggy application secret |
| `PLUGGY_ITEM_IDS` | Comma-separated identifiers of existing Items |

`PLUGGY_ITEM_ID` is accepted only as a temporary single-Item fallback when `PLUGGY_ITEM_IDS` is empty.

## Optional safety controls

| Variable | Default | Rule |
|---|---:|---|
| `PLUGGY_TIMEOUT_SECONDS` | `30` | Positive request timeout |
| `PLUGGY_MAX_RETRIES` | `2` | Non-negative retries for safe transient failures |
| `PLUGGY_MAX_PAGES` | `50` | Positive pagination page cap |
| `PLUGGY_MAX_PROVIDER_RECORDS` | `5000` | Positive provider-record safety cap per resource |
| `PLUGGY_MAX_WORKERS` | `4` | Positive fan-out concurrency, never above 4 |

`PLUGGY_BASE_URL` exists for controlled testing. Leave it unset for production so the official `https://api.pluggy.ai` host is used.

Credentials are never accepted as command-line flags. Store them using the environment or a secret manager appropriate to the host, then run `pluggy-finance doctor`.
