"""
pytest — determinismo global para todos os testes do WDO PROJECT 02.
"""

from __future__ import annotations

import pytest

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism


@pytest.fixture(scope="session", autouse=True)
def _wdo_project_session_determinism() -> int:
    """Limites de thread + seed no início da sessão."""
    return set_global_determinism(WDO_PROJECT_RANDOM_SEED)


@pytest.fixture(autouse=True)
def _wdo_project_per_test_determinism() -> int:
    """
    Reinicia seeds antes de CADA teste.

    Evita que testes anteriores avancem o RNG global e quebrem o stress 20x.
    """
    return set_global_determinism(WDO_PROJECT_RANDOM_SEED)
