# Troubleshooting

Start with:

```bash
pluggy-finance doctor
```

## Configuration error

Confirm that `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`, and at least one identifier in `PLUGGY_ITEM_IDS` are available to the same process. Do not paste their values into chat or command arguments.

## Authentication error

The client obtains an internal API key and renews it once after an unauthorized response. Persistent authentication errors usually mean the application credentials are invalid or the application cannot access the configured Item.

## Rate limit or network error

These failures are marked `retryable: true`. The client already performs a finite number of retries. Reduce Item scope, wait before running another, or lower fan-out with `PLUGGY_MAX_WORKERS`.

## Partial result

Use successful `items`, then inspect each `failures[].resource` to identify the Item, account, or investment that failed. Re-run only that narrowed scope when appropriate.

## Truncated result

Inspect `meta.pagination[].reason`. Increase `--limit` up to 500 for output truncation. For safety-cap truncation, narrow the Item/resource or date scope before changing environment caps.

## Empty bills

An empty successful bill response means Pluggy did not supply a bill for the selected credit account. It is not an error and must not be replaced with a computed or synthetic bill.
