"""
Interface abstrata para provedores financeiros.

Define o contrato que qualquer provedor (Pluggy, Belvo, etc.) deve
implementar. O Alfred jamais conhece o provedor específico — só
consome esta interface.
"""

from abc import ABC, abstractmethod
from typing import Optional
from models import Account, Transaction, CreditCard, Invoice, Investment


class FinancialProviderError(Exception):
    """Erro base do provider financeiro."""
    def __init__(self, message: str, code: str = "unknown", details: Optional[dict] = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(FinancialProviderError):
    """Erro de autenticação (token inválido/expirado)."""
    def __init__(self, message: str = "Falha de autenticação", details: Optional[dict] = None):
        super().__init__(message, code="auth_error", details=details)


class ConnectionError(FinancialProviderError):
    """Erro de conexão com o provedor."""
    def __init__(self, message: str = "Erro de conexão", details: Optional[dict] = None):
        super().__init__(message, code="connection_error", details=details)


class ConsentExpiredError(FinancialProviderError):
    """Consentimento expirado — precisa renovar."""
    def __init__(self, message: str = "Consentimento expirado. Reconecte o banco.", details: Optional[dict] = None):
        super().__init__(message, code="consent_expired", details=details)


class NotFoundError(FinancialProviderError):
    """Dado não encontrado."""
    def __init__(self, message: str = "Dado não encontrado", details: Optional[dict] = None):
        super().__init__(message, code="not_found", details=details)


class FinancialProvider(ABC):
    """Interface abstrata para acesso a dados financeiros.

    Implementações concretas devem conectar-se a um agregador
    (Pluggy, Belvo) que por sua vez acessa o Open Finance Brasil.
    """

    @abstractmethod
    def list_connections(self) -> list[dict]:
        """Lista todas as conexões bancárias ativas."""
        ...

    @abstractmethod
    def get_accounts(self) -> list[Account]:
        """Retorna todas as contas de todas as conexões."""
        ...

    @abstractmethod
    def get_account_balance(self, account_id: str) -> Account:
        """Retorna saldo atualizado de uma conta específica."""
        ...

    @abstractmethod
    def get_transactions(
        self,
        account_id: str,
        days: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[Transaction]:
        """Retorna transações de uma conta, com filtros opcionais de período."""
        ...

    @abstractmethod
    def get_credit_cards(self) -> list[CreditCard]:
        """Retorna todos os cartões de crédito disponíveis."""
        ...

    @abstractmethod
    def get_credit_card_invoices(self, card_account_id: str) -> list[Invoice]:
        """Retorna faturas de um cartão de crédito específico."""
        ...

    @abstractmethod
    def get_investments(self) -> list[Investment]:
        """Retorna todos os investimentos."""
        ...

    @abstractmethod
    def refresh_connection(self, item_id: str) -> bool:
        """Solicita atualização dos dados de uma conexão."""
        ...

    @abstractmethod
    def get_connection_status(self, item_id: str) -> dict:
        """Retorna status de uma conexão (ativo, expirado, etc.)."""
        ...