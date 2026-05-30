"""
pytest — determinismo global para todos os testes do WDO PROJECT 02.
"""

from __future__ import annotations

import pytest

from microstructure.determinism import WDO_PROJECT_RANDOM_SEED, set_global_determinism


@pytest.fixture(scope="session", autouse=True)
def _wdo_project_global_determinism() -> int:
    """Fixa seeds no início da sessão de testes."""
    return set_global_determinism(WDO_PROJECT_RANDOM_SEED)
