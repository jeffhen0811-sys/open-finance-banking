"""
Implementação concreta do FinancialProvider para a API Pluggy.

Usa o SDK oficial pluggy-sdk e o endpoint /auth para autenticação.

Devido a limitações do plano gratuito (não é possível listar items),
o item_id deve ser fornecido via variável de ambiente PLUGGY_ITEM_ID,
obtido uma vez a partir do Dashboard.

Referência: https://docs.pluggy.ai/reference
"""

import os
import time
import logging
from typing import Optional
from datetime import datetime, timedelta
from functools import cached_property

from pluggy_sdk import (
    ApiClient,
    Configuration,
    AuthApi,
    AuthRequest,
    ApiException,
    ItemsApi,
    AccountApi,
)
import requests

from financial_provider import (
    FinancialProvider,
    FinancialProviderError,
    AuthenticationError,
    ConnectionError,
    ConsentExpiredError,
    NotFoundError,
)
from models import Account, Transaction, CreditCard, Invoice, Investment
from cache import cached

logger = logging.getLogger(__name__)

# Endpoints via raw requests (SDK não expõe list/update)
BASE_URL = "https://api.pluggy.ai"
ITEMS_ENDPOINT = "/items"
ACCOUNTS_ENDPOINT = "/accounts"
TRANSACTIONS_ENDPOINT = "/v2/transactions"
INVESTMENTS_ENDPOINT = "/investments"
BILLS_ENDPOINT = "/bills"
IDENTITY_ENDPOINT = "/identity"

# Tempo de tolerância para renovação da apiKey (5 min antes de expirar)
API_KEY_TOLERANCE = 300


class PluggyProvider(FinancialProvider):
    """Provider financeiro via API Pluggy usando SDK oficial.

    Aceita um item_id fixo (já que o trial não permite listar items).
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        item_id: Optional[str] = None,
    ):
        self._client_id = client_id or os.environ.get("PLUGGY_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get("PLUGGY_CLIENT_SECRET", "")
        self._item_id = item_id or os.environ.get("PLUGGY_ITEM_ID", "")

        if not self._client_id or not self._client_secret:
            raise AuthenticationError(
                "PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET devem estar "
                "definidos nas variáveis de ambiente."
            )
        if not self._item_id:
            raise AuthenticationError(
                "PLUGGY_ITEM_ID deve estar definido. "
                "Copie o ID do item no Dashboard Pluggy."
            )

        # Configura SDK
        self._config = Configuration()
        self._client = ApiClient(self._config)
        self._api_key: Optional[str] = None

    # ------------------------------------------------------------------
    # Autenticação via SDK
    # ------------------------------------------------------------------

    def _ensure_api_key(self) -> str:
        """Obtém ou renova a apiKey via SDK (POST /auth)."""
        if self._api_key:
            return self._api_key

        logger.info("Solicitando nova apiKey via SDK (POST /auth)")
        try:
            auth_api = AuthApi(self._client)
            resp = auth_api.auth_create(auth_request=AuthRequest(
                client_id=self._client_id,
                client_secret=self._client_secret,
            ))
            self._api_key = resp.api_key
            # Configura apiKey no SDK para próximas chamadas
            self._config.api_key = {"X-API-KEY": self._api_key}
            logger.info("apiKey obtida com sucesso via SDK")
            return self._api_key
        except ApiException as exc:
            raise AuthenticationError(
                f"Falha ao obter apiKey Pluggy: {exc.status} - {exc.body[:200]}",
                details={"status": exc.status, "original_error": str(exc)},
            )

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Faz requisição autenticada usando a apiKey."""
        api_key = self._ensure_api_key()
        url = f"{BASE_URL}{endpoint}"
        headers = {"X-API-KEY": api_key}
        timeout = kwargs.pop("timeout", 30)

        try:
            resp = requests.request(
                method, url, headers=headers, timeout=timeout, **kwargs
            )
        except requests.Timeout:
            raise ConnectionError(
                f"Timeout na requisição: {method} {endpoint}",
                details={"endpoint": endpoint},
            )
        except requests.RequestException as exc:
            raise ConnectionError(
                f"Erro na requisição: {exc}",
                details={"endpoint": endpoint},
            )

        if resp.status_code == 401:
            # Força renovação na próxima chamada
            self._api_key = None
            raise AuthenticationError(
                "Token API expirou ou é inválido",
                details={"endpoint": endpoint},
            )
        elif resp.status_code == 404:
            raise NotFoundError(
                f"Recurso não encontrado: {endpoint}",
                details={"endpoint": endpoint},
            )
        elif resp.status_code == 422 or (
            resp.status_code == 403 and "consent" in resp.text.lower()
        ):
            raise ConsentExpiredError(
                "Conexão expirada. Reconecte o banco no Meu Pluggy.",
                details={"endpoint": endpoint},
            )
        elif resp.status_code >= 400:
            error_body = resp.text[:300] if resp.text else ""
            logger.warning(
                "Erro Pluggy API: %s %s -> %s: %s",
                method, endpoint, resp.status_code, error_body,
            )
            # Alguns 403 são esperados (trial não permite listar items)
            # mas não são críticos para operação normal
            if resp.status_code == 403 and "LIST_ITEMS" in resp.text:
                raise FinancialProviderError(
                    "Não é possível listar conexões neste plano. "
                    "Configure PLUGGY_ITEM_ID manualmente.",
                    code="list_not_enabled",
                    details={"endpoint": endpoint},
                )
            if resp.status_code == 410:
                logger.info("Endpoint deprecated, tentando alternativa")
                raise ConnectionError(
                    f"Endpoint deprecated: {endpoint}",
                    details={"endpoint": endpoint},
                )
            raise FinancialProviderError(
                f"Erro na API Pluggy ({resp.status_code})",
                code=f"http_{resp.status_code}",
                details={"endpoint": endpoint},
            )

        return resp.json()

    def _paginated_request(
        self, method: str, endpoint: str, params: Optional[dict] = None, **kwargs
    ) -> list[dict]:
        """Faz requisição paginada.

        Suporta:
        - cursor-based pagination (v2) com campo "next"
        - page-based pagination (v1) com "page"/"totalPages"
        """
        all_data = []
        page_params = dict(params or {})
        max_pages = 10  # segurança

        for _ in range(max_pages):
            data = self._request(method, endpoint, params=page_params, **kwargs)
            results = data.get("results", [])
            all_data.extend(results)

            # cursor-based (v2) — campo "next" com string
            next_cursor = data.get("next")
            if next_cursor:
                page_params["cursor"] = next_cursor
                continue

            # page-based (v1) — campo "page" como inteiro
            page = data.get("page")
            total_pages = data.get("totalPages", 1)
            current_page = page if isinstance(page, int) else page_params.get("page", 1)
            if current_page < total_pages:
                page_params["page"] = current_page + 1
                continue

            break

        return all_data

    # ------------------------------------------------------------------
    # Implementação da interface FinancialProvider
    # ------------------------------------------------------------------

    def list_connections(self) -> list[dict]:
        """Lista conexões — não disponível no trial.

        Retorna a conexão fixa configurada via PLUGGY_ITEM_ID.
        """
        try:
            # Tenta listar, mas retorna apenas o item fixo se falhar
            data = self._request("GET", f"/items/{self._item_id}")
            return [{
                "id": data.get("id"),
                "institution": "MeuPluggy (Itaú)",
                "status": data.get("status", "unknown"),
                "created_at": data.get("createdAt"),
                "updated_at": data.get("updatedAt"),
                "last_sync_at": data.get("lastUpdatedAt"),
                "execution_status": data.get("executionStatus", ""),
            }]
        except FinancialProviderError:
            return [{
                "id": self._item_id,
                "institution": "MeuPluggy",
                "status": "configured",
            }]

    @cached(ttl_seconds=300)
    def get_accounts(self) -> list[Account]:
        """Retorna contas do item fixo configurado."""
        try:
            accounts_data = self._paginated_request(
                "GET", ACCOUNTS_ENDPOINT,
                params={"itemId": self._item_id},
            )
        except (NotFoundError, ConsentExpiredError) as exc:
            logger.warning("Erro ao buscar contas: %s", exc)
            return []

        accounts: list[Account] = []
        for acc in accounts_data:
            acc_type = acc.get("type", "BANK")
            bank_data = acc.get("bankData") or {}

            if acc_type == "BANK":
                # Saldo está no nível principal da conta (balance)
                # e também em bankData.closingBalance
                balance = float(acc.get("balance", 0) or 0)
                closing = float(bank_data.get("closingBalance", balance) or balance)
                accounts.append(Account(
                    id=acc.get("id", ""),
                    institution="Itaú",
                    name=acc.get("name", "Conta Corrente"),
                    type="CHECKING",
                    currency=acc.get("currencyCode", "BRL"),
                    balance=balance,
                    available_balance=closing,
                ))
            elif acc_type == "SAVING":
                balance = float(acc.get("balance", 0) or 0)
                closing = float(bank_data.get("closingBalance", balance) or balance)
                accounts.append(Account(
                    id=acc.get("id", ""),
                    institution="Itaú",
                    name=acc.get("name", "Poupança"),
                    type="SAVING",
                    currency=acc.get("currencyCode", "BRL"),
                    balance=balance,
                    available_balance=closing,
                ))

        return accounts

    def get_account_balance(self, account_id: str) -> Account:
        """Retorna saldo de conta específica."""
        accounts = self.get_accounts()
        for acc in accounts:
            if acc.id == account_id:
                return acc
        raise NotFoundError(f"Conta {account_id} não encontrada")

    def get_transactions(
        self,
        account_id: str,
        days: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[Transaction]:
        """Retorna transações (v2 - cursor pagination)."""
        params: dict = {"accountId": account_id}

        if days:
            end = datetime.now()
            start = end - timedelta(days=days)
            params["dateFrom"] = start.strftime("%Y-%m-%d")
            params["dateTo"] = end.strftime("%Y-%m-%d")
        elif from_date and to_date:
            params["dateFrom"] = from_date
            params["dateTo"] = to_date

        try:
            raw = self._paginated_request(
                "GET", TRANSACTIONS_ENDPOINT, params=params,
            )
        except (NotFoundError, ConnectionError) as exc:
            logger.warning("Erro ao buscar transações: %s", exc)
            return []

        transactions: list[Transaction] = []
        for t in raw:
            amount = float(t.get("amount", 0) or 0)
            tx_type = "CREDIT" if amount > 0 else "DEBIT"

            transactions.append(Transaction(
                id=t.get("id", ""),
                account_id=account_id,
                date=t.get("date", ""),
                description=t.get("description", ""),
                amount=abs(amount),
                type=tx_type,
                category=t.get("category", ""),
                currency=t.get("currencyCode", "BRL"),
            ))

        return transactions

    def get_credit_cards(self) -> list[CreditCard]:
        """Retorna cartões de crédito das contas do item."""
        try:
            accounts_data = self._paginated_request(
                "GET", ACCOUNTS_ENDPOINT,
                params={"itemId": self._item_id},
            )
        except (NotFoundError, ConsentExpiredError):
            return []

        cards: list[CreditCard] = []
        for acc in accounts_data:
            if acc.get("type") != "CREDIT":
                continue

            credit_data = acc.get("creditData") or {}
            number = credit_data.get("number", "") or acc.get("number", "")
            last_four = number[-4:] if len(number) >= 4 else number

            cards.append(CreditCard(
                id=acc.get("id", ""),
                institution="Itaú",
                name=acc.get("name", ""),
                last_four_digits=last_four,
                limit=float(credit_data.get("creditLimit", 0) or 0),
                available_limit=float(credit_data.get("availableCreditLimit", 0) or 0),
            ))

        return cards

    def get_credit_card_invoices(self, card_account_id: str) -> list[Invoice]:
        """Retorna faturas de um cartão."""
        try:
            bills_data = self._paginated_request(
                "GET", BILLS_ENDPOINT,
                params={"accountId": card_account_id},
            )
        except (NotFoundError, ConnectionError):
            return []

        invoices: list[Invoice] = []
        for bill in bills_data:
            invoices.append(Invoice(
                card_id=card_account_id,
                closing_date=bill.get("closeDate", ""),
                due_date=bill.get("dueDate", ""),
                total=float(bill.get("totalAmount", 0) or 0),
                paid=float(bill.get("paidAmount", 0) or 0),
                status=bill.get("status", "OPEN"),
            ))

        return invoices

    def get_investments(self) -> list[Investment]:
        """Retorna investimentos do item fixo."""
        try:
            inv_data = self._paginated_request(
                "GET", INVESTMENTS_ENDPOINT,
                params={"itemId": self._item_id},
            )
        except (NotFoundError, ConnectionError):
            return []

        investments: list[Investment] = []
        for inv in inv_data:
            inv_type = self._map_investment_type(inv.get("type", ""))

            investments.append(Investment(
                id=inv.get("id", ""),
                institution="Itaú",
                type=inv_type,
                name=inv.get("name", ""),
                invested_amount=float(inv.get("amount", 0) or 0),
                current_value=float(inv.get("balance", 0) or 0),
                updated_at=inv.get("updatedAt", ""),
            ))

        return investments

    def refresh_connection(self, item_id: Optional[str] = None) -> bool:
        """Solicita sync — não disponível no trial."""
        logger.info("Sync manual não disponível no trial. Os dados atualizam automaticamente 1x/dia.")
        return False

    def get_connection_status(self, item_id: Optional[str] = None) -> dict:
        """Retorna status do item fixo."""
        item_id = item_id or self._item_id
        try:
            data = self._request("GET", f"{ITEMS_ENDPOINT}/{item_id}")
            return {
                "id": data.get("id"),
                "status": data.get("status", "unknown"),
                "execution_status": data.get("executionStatus", ""),
                "created_at": data.get("createdAt"),
                "last_sync_at": data.get("lastUpdatedAt"),
                "consent_expires_at": data.get("consent", {}).get("expiresAt"),
            }
        except (NotFoundError, FinancialProviderError):
            return {"id": item_id, "status": "error"}

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    @staticmethod
    def _map_investment_type(api_type: str) -> str:
        mapping = {
            "FIXED_INCOME": "FIXED_INCOME",
            "MUTUAL_FUND": "MUTUAL_FUND",
            "EQUITY": "EQUITY",
            "ETF": "ETF",
            "SECURITY": "SECURITY",
            "PENSION": "PENSION",
        }
        return mapping.get(api_type.upper(), api_type)