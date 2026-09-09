"""
Testes unitários para o provider financeiro Pluggy.

Usa mocking para evitar chamadas reais à API.
"""

import json
import unittest
from unittest.mock import MagicMock, patch
from typing import Any

# Adiciona o diretório da skill ao path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from models import Account, Transaction, CreditCard, Invoice, Investment
from financial_provider import (
    FinancialProvider,
    AuthenticationError,
    NotFoundError,
    ConsentExpiredError,
)
from cache import TTLCache, cached


# ---------------------------------------------------------------------------
# Testes dos modelos
# ---------------------------------------------------------------------------

class TestModels(unittest.TestCase):
    """Testa as dataclasses e seus métodos auxiliares."""

    def test_account_to_dict(self):
        acc = Account(
            id="acc_123",
            institution="Itaú",
            name="Conta Corrente",
            type="CHECKING",
            balance=1500.50,
            available_balance=1500.50,
        )
        d = acc.to_dict()
        self.assertEqual(d["id"], "acc_123")
        self.assertEqual(d["balance"], 1500.50)
        self.assertEqual(d["type"], "CHECKING")

    def test_account_type_br(self):
        acc = Account(id="1", institution="X", name="CC", type="CHECKING")
        self.assertEqual(acc.type_br(), "Conta Corrente")

        acc2 = Account(id="2", institution="X", name="CP", type="SAVING")
        self.assertEqual(acc2.type_br(), "Poupança")

    def test_transaction_type_br(self):
        t = Transaction(id="1", account_id="a1", date="2024-01-01",
                        description="Test", amount=100, type="DEBIT")
        self.assertEqual(t.type_br(), "Débito")

        t2 = Transaction(id="2", account_id="a1", date="2024-01-01",
                         description="Test", amount=50, type="CREDIT")
        self.assertEqual(t2.type_br(), "Crédito")

    def test_investment_profit_loss(self):
        inv = Investment(
            id="inv_1", institution="XP", type="FIXED_INCOME",
            name="Tesouro Selic", invested_amount=1000,
            current_value=1050, updated_at="2024-01-01",
        )
        self.assertEqual(inv.profit_loss(), 50.0)
        self.assertAlmostEqual(inv.profit_loss_pct(), 5.0)

    def test_investment_profit_loss_negative(self):
        inv = Investment(
            id="inv_2", institution="XP", type="EQUITY",
            name="PETR4", invested_amount=1000,
            current_value=800, updated_at="2024-01-01",
        )
        self.assertEqual(inv.profit_loss(), -200.0)
        self.assertAlmostEqual(inv.profit_loss_pct(), -20.0)

    def test_investment_zero_amount(self):
        inv = Investment(
            id="inv_3", institution="XP", type="FIXED_INCOME",
            name="Teste", invested_amount=0,
            current_value=0, updated_at="2024-01-01",
        )
        self.assertIsNone(inv.profit_loss_pct())

    def test_invoice_status_br(self):
        inv = Invoice(card_id="card_1", status="OPEN")
        self.assertEqual(inv.status_br(), "Aberta")

        inv2 = Invoice(card_id="card_1", status="PAID")
        self.assertEqual(inv2.status_br(), "Paga")

    def test_account_defaults(self):
        acc = Account(id="1", institution="X", name="C", type="CHECKING")
        self.assertEqual(acc.currency, "BRL")
        self.assertEqual(acc.balance, 0.0)
        self.assertEqual(acc.available_balance, 0.0)

    def test_transaction_defaults(self):
        t = Transaction(id="1", account_id="a1", date="2024-01-01",
                        description="Test", amount=100)
        self.assertEqual(t.type, "DEBIT")
        self.assertEqual(t.category, "")
        self.assertEqual(t.currency, "BRL")


# ---------------------------------------------------------------------------
# Testes do cache
# ---------------------------------------------------------------------------

class TestTTLCache(unittest.TestCase):
    """Testa o sistema de cache com TTL."""

    def setUp(self):
        self.cache = TTLCache()

    def test_set_and_get(self):
        self.cache.set("key1", "value1", 60)
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_get_expired(self):
        self.cache.set("key_expired", "value", -1)
        self.assertIsNone(self.cache.get("key_expired"))

    def test_get_missing(self):
        self.assertIsNone(self.cache.get("nao_existe"))

    def test_invalidate(self):
        self.cache.set("k", "v", 60)
        self.cache.invalidate("k")
        self.assertIsNone(self.cache.get("k"))

    def test_invalidate_all(self):
        self.cache.set("a", 1, 60)
        self.cache.set("b", 2, 60)
        self.cache.clear()
        self.assertIsNone(self.cache.get("a"))
        self.assertIsNone(self.cache.get("b"))

    def test_stats(self):
        self.cache.set("k1", "v1", 60)
        stats = self.cache.stats()
        self.assertEqual(stats["total_entries"], 1)
        self.assertEqual(stats["active"], 1)


# ---------------------------------------------------------------------------
# Testes dos modelos de erro do FinancialProvider
# ---------------------------------------------------------------------------

class TestFinancialErrors(unittest.TestCase):
    """Testa as hierarquias de erro."""

    def test_authentication_error(self):
        err = AuthenticationError("Token inválido")
        self.assertEqual(err.code, "auth_error")
        self.assertIn("Token", str(err))

    def test_consent_expired_error(self):
        err = ConsentExpiredError()
        self.assertEqual(err.code, "consent_expired")
        self.assertIn("Reconecte", str(err))

    def test_not_found_error(self):
        err = NotFoundError("Conta não encontrada")
        self.assertEqual(err.code, "not_found")

    def test_error_inheritance(self):
        err = ConsentExpiredError()
        self.assertIsInstance(err, Exception)


if __name__ == "__main__":
    unittest.main()
