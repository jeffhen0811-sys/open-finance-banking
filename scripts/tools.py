"""
Tools financeiras para consulta de dados bancários via Open Finance.

Cada função é uma tool que o Alfred pode chamar.
Retornam APENAS dados estruturados — NUNCA análises ou textos LLM.

Uso:
    from tools import FinancialToolsProvider
    tools = FinancialToolsProvider()
    accounts = tools.financial_get_accounts()
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from pluggy_provider import PluggyProvider
from models import FinancialSummary
from cache import cache_stats, invalidate_cache

logger = logging.getLogger(__name__)


class FinancialToolsProvider:
    """Provedor de tools financeiras para o Alfred."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        item_id: Optional[str] = None,
    ):
        self._provider = PluggyProvider(
            client_id=client_id,
            client_secret=client_secret,
            item_id=item_id,
        )

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def financial_get_accounts(self) -> dict:
        """Retorna todas as contas bancárias conectadas."""
        try:
            accounts = self._provider.get_accounts()
            return {
                "success": True,
                "accounts": [a.to_dict() for a in accounts],
                "count": len(accounts),
                "source_updated_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("financial_get_accounts failed: %s", exc)
            return {"success": False, "error": str(exc), "accounts": [], "count": 0}

    def financial_get_balances(self) -> dict:
        """Retorna saldos atuais de todas as contas."""
        try:
            accounts = self._provider.get_accounts()
            total_balance = sum(a.balance for a in accounts)
            total_available = sum(a.available_balance for a in accounts)

            return {
                "success": True,
                "accounts": [
                    {
                        "id": a.id,
                        "institution": a.institution,
                        "name": a.name,
                        "type": a.type,
                        "type_br": a.type_br(),
                        "balance": a.balance,
                        "available_balance": a.available_balance,
                        "currency": a.currency,
                    }
                    for a in accounts
                ],
                "total_balance": total_balance,
                "total_available": total_available,
                "accounts_count": len(accounts),
                "source_updated_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("financial_get_balances failed: %s", exc)
            return {"success": False, "error": str(exc), "accounts": [], "total_balance": 0, "total_available": 0}

    def financial_get_transactions(
        self,
        account_id: Optional[str] = None,
        days: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        description: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> dict:
        """Retorna transações com filtros opcionais.

        Se account_id não for informado, busca transações de TODAS as contas.
        """
        try:
            # Se não especificar conta, busca de todas
            if account_id:
                account_ids = [account_id]
            else:
                accounts = self._provider.get_accounts()
                account_ids = [a.id for a in accounts if a.type in ("CHECKING", "SAVING")]
                if not account_ids:
                    return {
                        "success": False,
                        "error": "Nenhuma conta bancária encontrada",
                        "transactions": [],
                        "count": 0,
                    }

            # Define período padrão (últimos 30 dias)
            if not days and not from_date:
                days = 30

            all_transactions = []
            for acc_id in account_ids:
                txns = self._provider.get_transactions(
                    account_id=acc_id,
                    days=days,
                    from_date=from_date,
                    to_date=to_date,
                )
                all_transactions.extend(txns)

            # Aplica filtros adicionais
            filtered = list(all_transactions)
            if min_amount is not None:
                filtered = [t for t in filtered if t.amount >= min_amount]
            if max_amount is not None:
                filtered = [t for t in filtered if t.amount <= max_amount]
            if description:
                desc_lower = description.lower()
                filtered = [t for t in filtered if desc_lower in t.description.lower()]
            if type_filter:
                filtered = [t for t in filtered if t.type == type_filter.upper()]

            # Ordena por data (mais recente primeiro)
            filtered.sort(key=lambda t: t.date, reverse=True)

            return {
                "success": True,
                "transactions": [t.to_dict() for t in filtered],
                "count": len(filtered),
                "total_count": len(all_transactions),
                "filters_applied": {
                    "account_id": account_id,
                    "days": days,
                    "from_date": from_date,
                    "to_date": to_date,
                    "min_amount": min_amount,
                    "max_amount": max_amount,
                    "description": description,
                    "type": type_filter,
                },
                "source_updated_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("financial_get_transactions failed: %s", exc)
            return {"success": False, "error": str(exc), "transactions": [], "count": 0}

    def financial_get_credit_cards(self) -> dict:
        """Retorna cartões de crédito disponíveis."""
        try:
            cards = self._provider.get_credit_cards()
            return {
                "success": True,
                "cards": [c.to_dict() for c in cards],
                "count": len(cards),
                "source_updated_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("financial_get_credit_cards failed: %s", exc)
            return {"success": False, "error": str(exc), "cards": [], "count": 0}

    def financial_get_credit_card_invoice(self, card_id: str) -> dict:
        """Retorna fatura de um cartão de crédito."""
        try:
            invoices = self._provider.get_credit_card_invoices(card_id)
            return {
                "success": True,
                "card_id": card_id,
                "invoices": [inv.to_dict() for inv in invoices],
                "count": len(invoices),
                "current_invoice": invoices[0].to_dict() if invoices else None,
                "source_updated_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("financial_get_credit_card_invoice failed: %s", exc)
            return {"success": False, "error": str(exc), "invoices": [], "count": 0}

    def financial_get_investments(self) -> dict:
        """Retorna investimentos."""
        try:
            investments = self._provider.get_investments()
            total_invested = sum(i.invested_amount for i in investments)
            total_value = sum(i.current_value for i in investments)

            return {
                "success": True,
                "investments": [
                    {
                        **i.to_dict(),
                        "profit_loss": i.profit_loss(),
                        "profit_loss_pct": i.profit_loss_pct(),
                        "type_br": i.type_br(),
                    }
                    for i in investments
                ],
                "count": len(investments),
                "total_invested": total_invested,
                "total_current_value": total_value,
                "total_profit_loss": total_value - total_invested,
                "source_updated_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("financial_get_investments failed: %s", exc)
            return {"success": False, "error": str(exc), "investments": [], "count": 0}

    def financial_get_summary(self, days: int = 30) -> dict:
        """Produz dados estruturados para resumo financeiro."""
        try:
            accounts = self._provider.get_accounts()
            cards = self._provider.get_credit_cards()
            investments = self._provider.get_investments()

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Transações do período (de todas as contas bancárias)
            all_txns = []
            for acc in accounts:
                if acc.type in ("CHECKING", "SAVING"):
                    txns = self._provider.get_transactions(
                        account_id=acc.id,
                        from_date=start_date.strftime("%Y-%m-%d"),
                        to_date=end_date.strftime("%Y-%m-%d"),
                    )
                    all_txns.extend(txns)

            total_income = sum(t.amount for t in all_txns if t.type == "CREDIT")
            total_expenses = sum(t.amount for t in all_txns if t.type == "DEBIT")

            # Faturas: invoice mais recente de cada cartão
            invoices_data = []
            for card in cards:
                invs = self._provider.get_credit_card_invoices(card.id)
                if invs:
                    invoices_data.append(invs[0].to_dict())

            summary = FinancialSummary(
                total_balance=sum(a.balance for a in accounts),
                total_available=sum(a.available_balance for a in accounts),
                accounts_count=len(accounts),
                accounts=[a.to_dict() for a in accounts],
                total_invested=sum(i.invested_amount for i in investments),
                total_investment_value=sum(i.current_value for i in investments),
                investments_count=len(investments),
                investments=[i.to_dict() for i in investments],
                total_credit_limit=sum(c.limit for c in cards),
                total_credit_available=sum(c.available_limit for c in cards),
                cards_count=len(cards),
                cards=[c.to_dict() for c in cards],
                total_invoice=sum(i.get("total", 0) for i in invoices_data),
                invoices=invoices_data,
                total_income=total_income,
                total_expenses=total_expenses,
                transactions_count=len(all_txns),
                period_start=start_date.strftime("%Y-%m-%d"),
                period_end=end_date.strftime("%Y-%m-%d"),
            )

            return {"success": True, **summary.to_dict(), "source_updated_at": datetime.now().isoformat()}
        except Exception as exc:
            logger.error("financial_get_summary failed: %s", exc)
            return {"success": False, "error": str(exc)}


# Instância global singleton
_tools_instance: Optional[FinancialToolsProvider] = None


def get_tools() -> FinancialToolsProvider:
    """Retorna instância singleton do FinancialToolsProvider."""
    global _tools_instance
    if _tools_instance is None:
        _tools_instance = FinancialToolsProvider()
    return _tools_instance