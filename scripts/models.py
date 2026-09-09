"""
Modelos normalizados para dados financeiros.

Todos os schemas são compartilhados entre providers, garantindo que
o Alfred nunca precise conhecer o formato específico de cada banco.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Tipos de conta
# ---------------------------------------------------------------------------

ACCOUNT_TYPES = {
    "CHECKING": "Conta Corrente",
    "SAVING": "Poupança",
    "INVESTMENT": "Conta Investimento",
    "PAYMENT": "Conta de Pagamento",
}

INVESTMENT_TYPES = {
    "FIXED_INCOME": "Renda Fixa",
    "MUTUAL_FUND": "Fundos de Investimento",
    "EQUITY": "Ações",
    "ETF": "ETF",
    "REAL_ESTATE": "Imóveis",
    "SECURITY": "Títulos (Security)",
    "COE": "COE",
    "PENSION": "Previdência",
}

INVOICE_STATUS = {
    "OPEN": "Aberta",
    "PAID": "Paga",
    "OVERDUE": "Vencida",
    "CLOSED": "Fechada",
}

TRANSACTION_TYPES = {
    "DEBIT": "Débito",
    "CREDIT": "Crédito",
}


# ---------------------------------------------------------------------------
# Dataclasses normalizadas
# ---------------------------------------------------------------------------

@dataclass
class Account:
    """Conta bancária normalizada."""
    id: str
    institution: str
    name: str
    type: str  # CHECKING | SAVING | INVESTMENT | PAYMENT
    currency: str = "BRL"
    balance: float = 0.0
    available_balance: float = 0.0

    def type_br(self) -> str:
        return ACCOUNT_TYPES.get(self.type, self.type)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Transaction:
    """Transação financeira normalizada."""
    id: str
    account_id: str
    date: str
    description: str
    amount: float
    type: str = "DEBIT"  # DEBIT | CREDIT
    category: str = ""
    currency: str = "BRL"

    def type_br(self) -> str:
        return TRANSACTION_TYPES.get(self.type, self.type)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CreditCard:
    """Cartão de crédito normalizado."""
    id: str
    institution: str
    name: str
    last_four_digits: str = ""
    limit: float = 0.0
    available_limit: float = 0.0
    currency: str = "BRL"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Invoice:
    """Fatura de cartão de crédito normalizada."""
    card_id: str
    closing_date: str = ""
    due_date: str = ""
    total: float = 0.0
    paid: float = 0.0
    status: str = "OPEN"  # OPEN | PAID | OVERDUE | CLOSED

    def status_br(self) -> str:
        return INVOICE_STATUS.get(self.status, self.status)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Investment:
    """Investimento normalizado."""
    id: str
    institution: str
    type: str
    name: str
    invested_amount: float = 0.0
    current_value: float = 0.0
    updated_at: str = ""
    currency: str = "BRL"

    def type_br(self) -> str:
        return INVESTMENT_TYPES.get(self.type, self.type)

    def profit_loss(self) -> float:
        return self.current_value - self.invested_amount

    def profit_loss_pct(self) -> Optional[float]:
        if self.invested_amount > 0:
            return ((self.current_value - self.invested_amount) / self.invested_amount) * 100
        return None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Resumo financeiro (composto)
# ---------------------------------------------------------------------------

@dataclass
class FinancialSummary:
    """Resumo consolidado das finanças."""
    total_balance: float = 0.0
    total_available: float = 0.0
    accounts_count: int = 0
    accounts: list[dict] = field(default_factory=list)

    total_invested: float = 0.0
    total_investment_value: float = 0.0
    investments_count: int = 0
    investments: list[dict] = field(default_factory=list)

    total_credit_limit: float = 0.0
    total_credit_available: float = 0.0
    cards_count: int = 0
    cards: list[dict] = field(default_factory=list)

    total_invoice: float = 0.0
    invoices: list[dict] = field(default_factory=list)

    total_income: float = 0.0
    total_expenses: float = 0.0
    transactions_count: int = 0

    period_start: str = ""
    period_end: str = ""

    def to_dict(self) -> dict:
        return asdict(self)