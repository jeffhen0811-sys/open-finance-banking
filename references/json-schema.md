# JSON response contract

Every data command emits one compact JSON document:

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

## Status

- `success`: no requested resource failed, including a legitimate empty result.
- `partial`: at least one resource succeeded and at least one failed.
- `error`: no requested record succeeded and a failure occurred.

Complete failure exits with code 1. Successful and partial documents exit with code 0.

## Metadata

- `count` is the number of emitted normalized records.
- `truncated` is true when the output limit or a provider pagination safety cap stopped complete traversal.
- `filters` records effective scope, date, type, text, amount, and limit filters.
- `freshness` contains provider-supplied Item update timestamps. Request time is not source freshness.
- `pagination_summary`, when resources paginate, aggregates resource and page counts by pagination and source kind.
- `pagination` contains only actionable resource details: multiple pages, truncation, or a pagination anomaly. Normal single-page reads are omitted from this array.

## Failures

Each failure contains a stable `code`, English `message`, `retryable` boolean, and resource identifiers. Optional `details` contain safe status or retry information, never provider response bodies or credentials.

Stable codes include `configuration_error`, `authentication_error`, `validation_error`, `rate_limit_error`, `network_error`, `provider_error`, `pagination_error`, and `unexpected_response`.

## Raw fields

`--raw` adds the provider object under each normalized record's `raw` field. Sensitive keys are recursively replaced with `[REDACTED]`. Normalized fields remain authoritative for routine automation.
