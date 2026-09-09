# Open Finance Banking — Skill for Hermes Agent

Skill to query Brazilian bank accounts via **Open Finance Brasil** using **Pluggy** (Meu Pluggy — free personal tier). Read-only, secure, structured.

## Features

| Tool | Description |
|------|-------------|
| `financial_get_accounts()` | List all bank accounts (checking, savings) |
| `financial_get_balances()` | Current balances for all accounts |
| `financial_get_transactions()` | Transactions with date/amount/description filters |
| `financial_get_credit_cards()` | Available credit cards |
| `financial_get_credit_card_invoice()` | Invoice for a specific card |
| `financial_get_investments()` | Current investment balances |
| `financial_get_summary()` | Consolidated financial summary |

## Quick Start

```python
import sys
sys.path.insert(0, "path/to/open-finance-banking/scripts")
from tools import FinancialToolsProvider

tools = FinancialToolsProvider()
accounts = tools.financial_get_accounts()
```

Requires `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`, `PLUGGY_ITEM_ID` env vars.

## License

MIT