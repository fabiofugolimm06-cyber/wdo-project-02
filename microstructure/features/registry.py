from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, Type

logger = logging.getLogger(__name__)

_SKIP_MODULES = {"base", "registry", "datasets", "__init__"}


class Registry:
    def __init__(self):
        self._items: Dict[str, Type] = {}

    def register(self, cls):
        name = getattr(cls, "name", cls.__name__)
        if not name or not str(name).strip():
            raise ValueError(
                f"FeatureRegistry: name inválido para {cls.__name__!r}."
            )
        if name in self._items and self._items[name] is not cls:
            raise ValueError(
                f"FeatureRegistry: name duplicado '{name}' — "
                f"já registrado como {self._items[name].__name__}, "
                f"tentativa de registrar {cls.__name__}."
            )
        self._items[name] = cls
        return cls

    def list(self) -> list[str]:
        if not self._items:
            autodiscover()
        return sorted(self._items.keys())

    def get(self, name: str):
        if name not in self._items:
            raise KeyError(
                f"Feature '{name}' not found. Available: {self.list()}"
            )
        return self._items[name]

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"Registry(n={len(self)}, features={self.list()})"


REGISTRY = Registry()


def register_feature(cls):
    """Decorator: registers a BaseFeature subclass in the global REGISTRY."""
    return REGISTRY.register(cls)


def lock():
    # no-op — kept for pipeline compatibility
    return True


def autodiscover() -> list[str]:
    """
    Import every module inside `microstructure.features` that is not
    in _SKIP_MODULES.  Each module's @register_feature decorators run
    at import time, populating REGISTRY automatically.

    Returns the sorted list of registered feature names after discovery.

    Example
    -------
    >>> from microstructure.features.registry import autodiscover, REGISTRY
    >>> autodiscover()
    ['delta', ...]
    >>> REGISTRY.list()
    ['delta', ...]
    """
    import microstructure.features as pkg

    pkg_path = pkg.__path__
    pkg_name = pkg.__name__

    errors: list[str] = []

    discovered = sorted(
        module_name
        for _, module_name, _ in pkgutil.iter_modules(pkg_path)
        if module_name not in _SKIP_MODULES
    )
    for module_name in discovered:
        full_name = f"{pkg_name}.{module_name}"
        try:
            importlib.import_module(full_name)
            logger.debug("[autodiscover] imported %s", full_name)
        except Exception as exc:
            msg = f"{full_name}: {exc}"
            errors.append(msg)
            logger.warning("[autodiscover] failed to import %s", msg)

    # Fallback explícito — delta é a feature mínima do pipeline
    if "delta" not in REGISTRY:
        try:
            importlib.import_module(f"{pkg_name}.delta")
        except Exception as exc:
            errors.append(f"{pkg_name}.delta (fallback): {exc}")

    if not REGISTRY._items and errors:
        raise RuntimeError(
            "autodiscover(): nenhuma feature registrada. Falhas de import:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    names = validate_registry()
    return names


def validate_registry() -> list[str]:
    """
    Valida consistência do REGISTRY após autodiscover.

    Raises
    ------
    RuntimeError : registry vazio ou nomes duplicados (inconsistência interna).
    """
    items = REGISTRY._items
    names = sorted(items.keys())
    if len(names) != len(set(names)):
        raise RuntimeError(
            "validate_registry: nomes duplicados detectados no REGISTRY."
        )
    if not names:
        raise RuntimeError(
            "validate_registry: REGISTRY vazio — nenhuma feature registrada."
        )
    for name, cls in items.items():
        declared = getattr(cls, "name", None)
        if declared and declared != name:
            logger.warning(
                "[validate_registry] '%s': cls.name=%r difere da chave do registry.",
                name,
                declared,
            )
    logger.debug("[validate_registry] OK — %d features: %s", len(names), names)
    return names


def ensure_features_registered() -> list[str]:
    """Garante registry populado; retorna lista de features."""
    if len(REGISTRY) == 0:
        autodiscover()
    return validate_registry()


def _bootstrap_registry() -> None:
    """Popula REGISTRY na importação do módulo (REGISTRY.list() → ['delta', ...])."""
    try:
        ensure_features_registered()
    except Exception as exc:
        logger.warning(
            "[registry] bootstrap falhou (chame autodiscover() manualmente): %s",
            exc,
        )


_bootstrap_registry()