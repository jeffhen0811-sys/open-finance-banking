"""
Persistência local de conexões financeiras.

Armazena informações das conexões (items) em um arquivo JSON no
diretório data/ da skill. Armazena apenas metadados — NUNCA tokens
ou credenciais bancárias.

Estrutura:
  ~/.hermes/state/open-finance-banking/connections.json

Para evitar expor dados, tokens de acesso são gerenciados pelo
provider (apiKey expira em 2h e é renovada automaticamente).
"""

import os
import json
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Diretório de dados da skill
SKILL_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
)
CONNECTIONS_FILE = os.path.join(SKILL_DATA_DIR, "connections.json")


def _ensure_data_dir() -> str:
    """Cria o diretório de dados se não existir."""
    os.makedirs(SKILL_DATA_DIR, exist_ok=True)
    return SKILL_DATA_DIR


def _load_connections() -> list[dict]:
    """Carrega conexões do arquivo JSON."""
    _ensure_data_dir()
    if not os.path.exists(CONNECTIONS_FILE):
        return []
    try:
        with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as exc:
        logger.warning("Erro ao ler connections.json: %s", exc)
        return []


def _save_connections(connections: list[dict]):
    """Salva conexões no arquivo JSON."""
    _ensure_data_dir()
    try:
        with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(connections, f, indent=2, ensure_ascii=False)
    except IOError as exc:
        logger.error("Erro ao salvar connections.json: %s", exc)


def register_connection(item_id: str, institution: str, status: str = "active"):
    """Registra uma nova conexão bancária."""
    connections = _load_connections()

    # Atualiza se já existir
    for conn in connections:
        if conn["item_id"] == item_id:
            conn.update({
                "institution": institution,
                "status": status,
                "updated_at": datetime.now().isoformat(),
            })
            _save_connections(connections)
            return

    # Adiciona nova
    connections.append({
        "item_id": item_id,
        "institution": institution,
        "status": status,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    _save_connections(connections)


def update_connection_status(item_id: str, status: str, consent_expires_at: Optional[str] = None):
    """Atualiza o status de uma conexão."""
    connections = _load_connections()
    for conn in connections:
        if conn["item_id"] == item_id:
            conn["status"] = status
            conn["updated_at"] = datetime.now().isoformat()
            if consent_expires_at:
                conn["consent_expires_at"] = consent_expires_at
            _save_connections(connections)
            return


def get_connections() -> list[dict]:
    """Retorna todas as conexões registradas."""
    return _load_connections()


def get_active_connections() -> list[dict]:
    """Retorna apenas conexões ativas."""
    return [c for c in _load_connections() if c.get("status") == "active"]


def remove_connection(item_id: str):
    """Remove uma conexão."""
    connections = _load_connections()
    connections = [c for c in connections if c["item_id"] != item_id]
    _save_connections(connections)


def has_expired_connections() -> bool:
    """Verifica se há conexões com consentimento expirado."""
    now = datetime.now().isoformat()
    for conn in _load_connections():
        expires = conn.get("consent_expires_at")
        if expires and expires < now:
            return True
    return False