## Purpose

Provide agents with a concise, deterministic, and read-only interface for querying personal financial data collected by Pluggy without requiring knowledge of provider identifiers, pagination details, or internal Python modules.

## ADDED Requirements

### Requirement: English-only maintained content
All maintained skill content MUST be written in English, including instructions, references, source code identifiers, command and option names, output fields, status and error messages, fixtures, and tests.

#### Scenario: Agent loads the skill
- **WHEN** an agent reads the skill instructions or a referenced resource
- **THEN** every maintained instruction and example is presented in English

#### Scenario: Command reports a failure
- **WHEN** a command returns validation, authentication, provider, or partial-result information
- **THEN** all machine-readable fields and human-readable messages are in English

### Requirement: Direct agent-facing command interface
The system SHALL expose a documented `pluggy-finance` command interface that can be invoked without importing Python modules or constructing provider objects.

#### Scenario: Agent performs a routine query
- **WHEN** an agent invokes a supported command with valid configuration
- **THEN** the command performs the query and writes one JSON document to standard output

#### Scenario: Agent requests command help
- **WHEN** an agent invokes command help
- **THEN** the system lists supported commands, required inputs, optional filters, and examples in English

### Requirement: Stable JSON response envelope
Every command SHALL return a stable JSON envelope containing an outcome indicator, result data, response metadata, and structured failures where applicable.

#### Scenario: Query succeeds
- **WHEN** all required Pluggy resources are retrieved successfully
- **THEN** the response indicates success and includes `items`, `meta`, and an empty `failures` collection

#### Scenario: Query is partially successful
- **WHEN** one or more resources fail while other resources succeed
- **THEN** the response indicates a partial outcome, preserves successful results, and identifies each failed resource with a stable error code and retryability indicator

#### Scenario: Query fails completely
- **WHEN** no requested resource can be retrieved
- **THEN** the response indicates failure and contains a structured error without presenting an empty result as a successful query

### Requirement: Safe Pluggy authentication
The system SHALL authenticate with Pluggy using configured client credentials, keep API keys internal, renew an expired API key, and avoid exposing secrets in output or logs.

#### Scenario: Valid credentials are configured
- **WHEN** a command requires Pluggy data and no valid API key is cached in the current process
- **THEN** the system obtains an API key and uses it internally for the request

#### Scenario: API key expires during a query
- **WHEN** Pluggy rejects a request because the API key expired
- **THEN** the system obtains a new API key and retries the failed request once

#### Scenario: Credentials are invalid or missing
- **WHEN** required credentials are absent or rejected
- **THEN** the command returns a non-success outcome with an actionable error and does not include credential values

### Requirement: Read-only financial access
The system MUST restrict its Pluggy operations to authentication and retrieval of financial resources; it MUST NOT create, update, synchronize, categorize, or delete financial resources or connections.

#### Scenario: Agent queries financial data
- **WHEN** any supported data command executes
- **THEN** all financial-resource requests use retrieval operations only

#### Scenario: Agent requests a mutation
- **WHEN** a request would move money or create, update, synchronize, categorize, or delete Pluggy data
- **THEN** the skill refuses the operation and explains that it is read-only

### Requirement: Connection diagnostics
The system SHALL provide a diagnostic command that validates local configuration, authentication, Item accessibility, and data freshness without returning financial transaction payloads.

#### Scenario: Configuration is healthy
- **WHEN** the diagnostic command can authenticate and retrieve every configured Item
- **THEN** it reports a successful status and the latest provider synchronization timestamp for each Item

#### Scenario: Item is inaccessible
- **WHEN** a configured Item cannot be retrieved
- **THEN** the diagnostic response identifies the Item, the failure category, retryability, and a safe corrective action

### Requirement: Account and credit-card discovery
The system SHALL list all collected Pluggy accounts and preserve each resource's Item identifier, account identifier, provider type, provider subtype, institution, name, currency, balance, and type-specific balance or credit-limit fields when available.

#### Scenario: Item contains bank and credit accounts
- **WHEN** the accounts command runs without a type filter
- **THEN** both bank accounts and credit-card accounts are returned

#### Scenario: Account type filter is provided
- **WHEN** the caller filters for bank or credit accounts
- **THEN** only matching resources are returned without changing their provider type or subtype

### Requirement: Bank and credit-card transaction search
The system SHALL search Pluggy account transactions for bank accounts, credit-card accounts, one explicit account, or all matching accounts while preserving signed amount, provider-supplied direction, status, date, description, currency, category, account context, and available credit-card metadata.

#### Scenario: Search all transactions
- **WHEN** the transaction command is invoked with an all-account scope and no account identifier
- **THEN** the system discovers bank and credit accounts and aggregates matching transactions across them

#### Scenario: Search credit-card purchases
- **WHEN** the transaction command is invoked with credit scope and a date range
- **THEN** transactions for credit accounts are returned with their original amount, direction, status, and installment metadata

#### Scenario: Search one account
- **WHEN** a valid account identifier is provided
- **THEN** only transactions belonging to that account are queried and returned

#### Scenario: Transaction filters are provided
- **WHEN** the caller supplies a date range, status, direction, description, or amount filter
- **THEN** the response contains only matching transactions and reports the applied filters in metadata

### Requirement: Credit-card bill retrieval
The system SHALL retrieve bills for one credit-card account or for all discovered credit-card accounts and preserve bill identifiers, dates, amounts, status, account context, and provider freshness when available.

#### Scenario: Retrieve bills for all cards
- **WHEN** the bills command is invoked without an account identifier
- **THEN** the system discovers all credit accounts and returns their collected bills

#### Scenario: Open bill is not supplied by the institution
- **WHEN** Pluggy has no collected open bill for a credit account
- **THEN** the response distinguishes an empty provider result from a retrieval failure and does not synthesize a bill

### Requirement: Investment position retrieval
The system SHALL list investment positions for one configured Item or all configured Items while preserving provider identifiers, type, subtype, name, currency, current balance, original or invested amount, profit, withdrawal amount, status, and relevant dates when available.

#### Scenario: Retrieve all investments
- **WHEN** the investments command is invoked without a type filter
- **THEN** all collected investment positions are returned without replacing provider types with hard-coded institution values

#### Scenario: Investment type filter is provided
- **WHEN** the caller specifies a supported investment type
- **THEN** only matching positions are returned and the filter is reported in response metadata

### Requirement: Investment transaction search
The system SHALL retrieve paginated movements for one investment or all discovered investments and support local filtering by date and movement type when those filters are unavailable from the provider endpoint.

#### Scenario: Search one investment
- **WHEN** an investment identifier is provided
- **THEN** all matching pages for that investment are traversed subject to configured safety limits

#### Scenario: Search all investment movements by date
- **WHEN** no investment identifier is provided and a date range is supplied
- **THEN** the system discovers investments, retrieves their movements, and returns only movements within the requested range

### Requirement: Unified financial activity
The system SHALL provide a unified activity query that combines bank transactions, credit-card transactions, and investment movements into a chronological result with an explicit source kind for every record.

#### Scenario: Query recent activity
- **WHEN** the activity command is invoked for a date range
- **THEN** matching bank, credit-card, and investment records are returned in descending chronological order

#### Scenario: One activity source fails
- **WHEN** one source cannot be retrieved but other sources succeed
- **THEN** successful activity is returned with a partial outcome and the failed source is identified

### Requirement: Bounded and inspectable output
List and search commands SHALL apply a documented default result limit, report truncation, and allow callers to request a different safe limit or opt into raw provider fields.

#### Scenario: Results exceed the default limit
- **WHEN** a query finds more records than the default response limit
- **THEN** only the bounded number of records is emitted and metadata reports that the result was truncated

#### Scenario: Raw output is not requested
- **WHEN** a query uses default output mode
- **THEN** provider payload fields that are not part of the stable contract are omitted

#### Scenario: Raw output is requested
- **WHEN** the caller explicitly enables raw output
- **THEN** available provider fields are included without exposing authentication material

### Requirement: Correct and complete pagination
The system SHALL follow Pluggy's endpoint-specific pagination contract, prevent pagination loops, and make incomplete traversal visible instead of silently returning a complete-looking result.

#### Scenario: Cursor-based transaction response has a next page
- **WHEN** Pluggy returns a `next` query containing an `after` cursor
- **THEN** the next transaction page is requested according to that query until completion or a declared safety boundary

#### Scenario: Page-based resource has additional pages
- **WHEN** a Pluggy response reports a current page below the total number of pages
- **THEN** subsequent pages are requested until completion or a declared safety boundary

#### Scenario: Safety boundary stops pagination
- **WHEN** a configured page or record boundary is reached before provider pagination completes
- **THEN** metadata marks the result as incomplete and returns a continuation or actionable explanation

### Requirement: Efficient multi-resource execution
The system SHALL avoid redundant discovery and authentication calls within one invocation and SHALL perform independent per-account or per-investment reads concurrently within a bounded concurrency limit.

#### Scenario: Query spans multiple accounts
- **WHEN** a transaction or bill query targets multiple accounts
- **THEN** account discovery occurs once and independent resource reads run with bounded concurrency

#### Scenario: Composite activity query executes
- **WHEN** unified activity requires accounts and investments
- **THEN** shared discovery results are reused rather than retrieved separately for each activity source

### Requirement: Agent-oriented skill guidance
The skill instructions SHALL direct agents to the shortest command for common questions, avoid requiring reference documents during normal operation, and load setup or API references only for configuration or troubleshooting.

#### Scenario: User asks a common financial question
- **WHEN** the request maps directly to a supported command
- **THEN** the agent can select and invoke that command using only `SKILL.md`

#### Scenario: Command reports a configuration problem
- **WHEN** normal execution fails because local setup is incomplete
- **THEN** the skill directs the agent to diagnostics and the setup reference
