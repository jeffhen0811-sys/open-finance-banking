"""
Sistema de cache simples com TTL.

Armazena resultados de chamadas frequentes (saldos, transações)
em memória com tempo de expiração configurável. Reduz chamadas
desnecessárias à API Pluggy.

Nunca apresenta dados em cache como se fossem tempo real —
sempre inclui source_updated_at/metadados de frescor.
"""

import time
import logging
from typing import Any, Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class _CacheEntry:
    """Entrada individual do cache."""
    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.expires_at = time.time() + ttl

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - (self.expires_at - self._ttl)

    def __init__(self, value: Any, ttl: float):
        self.value = value
        self._ttl = ttl
        self.created_at = time.time()
        self.expires_at = time.time() + ttl


class TTLCache:
    """Cache em memória com TTL por chave.

    Thread-safe para operações básicas de leitura/escrita.
    """

    def __init__(self):
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        """Retorna valor da cache se válido, None se expirado/ausente."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._store[key]
            logger.debug("Cache expired for key: %s", key)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float):
        """Armazena valor com TTL em segundos."""
        self._store[key] = _CacheEntry(value, ttl_seconds)
        logger.debug("Cache set for key: %s, TTL: %ss", key, ttl_seconds)

    def invalidate(self, key: str):
        """Remove uma chave específica do cache."""
        self._store.pop(key, None)
        logger.debug("Cache invalidated for key: %s", key)

    def invalidate_all(self):
        """Limpa todo o cache."""
        self._store.clear()
        logger.debug("Cache fully invalidated")

    def clear(self):
        self.invalidate_all()

    def stats(self) -> dict:
        """Estatísticas do cache."""
        now = time.time()
        active = sum(1 for e in self._store.values() if not e.is_expired)
        expired = sum(1 for e in self._store.values() if e.is_expired)
        return {
            "total_entries": len(self._store),
            "active": active,
            "expired": expired,
        }


# Instância global única de cache
_global_cache = TTLCache()


def cached(ttl_seconds: float = 300):
    """Decorator para cache automático em método de instância.

    A chave é composta por: <class_name>.<method_name>.<args_hash>

    Uso:
        @cached(ttl_seconds=300)
        def get_accounts(self) -> list[Account]:
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Gera chave única
            key_parts = [
                self.__class__.__name__,
                func.__name__,
            ]
            if args:
                key_parts.append(str(args))
            if kwargs:
                key_parts.append(str(sorted(kwargs.items())))
            cache_key = ".".join(key_parts)

            # Tenta cache
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache HIT for %s", cache_key)
                return cached_value

            # Executa função e armazena
            logger.debug("Cache MISS for %s", cache_key)
            result = func(self, *args, **kwargs)

            # Só cacheia se o resultado não for vazio
            if result is not None:
                _global_cache.set(cache_key, result, ttl_seconds)

            return result
        return wrapper
    return decorator


def invalidate_cache(pattern: Optional[str] = None):
    """Invalida entradas do cache que contenham o padrão.

    Se pattern for None, limpa tudo.
    """
    if pattern is None:
        _global_cache.clear()
        return

    keys_to_remove = [
        k for k in _global_cache._store if pattern in k
    ]
    for k in keys_to_remove:
        _global_cache.invalidate(k)


def cache_stats() -> dict:
    """Retorna estatísticas do cache global."""
    return _global_cache.stats()