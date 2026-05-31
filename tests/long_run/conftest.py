"""Marca todos os testes em ``tests/long_run/`` como ``@pytest.mark.long``."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.path.parent.name == "long_run":
            item.add_marker(pytest.mark.long)
