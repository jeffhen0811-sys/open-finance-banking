# Pagination and bounded output

Pluggy uses two pagination families. They are intentionally handled separately.

## Cursor-based transactions

`GET /v2/transactions` returns `results` and an optional top-level `next` query such as `?accountId=...&after=...`. The client parses that query and passes the decoded `after` value on the next GET request. It stops on provider exhaustion, the output limit when safe, the page cap, the provider-record cap, an invalid continuation, or a repeated continuation.

## Page-based resources

Accounts, bills, investments, and investment transactions return `page`, `totalPages`, and `results`. The client advances through every page until provider exhaustion or a declared safety boundary.

## Completeness

`meta.truncated` is true whenever traversal or final output is incomplete. `meta.pagination_summary` reports aggregate resource and page counts. `meta.pagination` keeps only resources that read multiple pages or stopped for an actionable reason, so successful single-page fan-out does not fill the response with repetitive entries.

An actionable `meta.pagination[].reason` can be `output_limit`, `max_pages`, `max_provider_records`, `repeated_page`, `repeated_continuation`, or `invalid_continuation`.

Investment movement date and type filters are local, so pagination occurs before filtering. Default output is 100 records, the CLI maximum is 500, and the independent provider safety cap defaults to 5,000 records per resource.
