"""
tests/long_run/test_rollback_stress.py
"""

from __future__ import annotations

import pytest

from src.certification import LongRunValidator
from src.deployment import VersionManager


@pytest.fixture(autouse=True)
def _reset():
    VersionManager.reset()
    from src.certification.system_certificate import CertificateRegistry

    CertificateRegistry.reset()
    yield
    VersionManager.reset()
    CertificateRegistry.reset()


class TestRollbackStress:
    def test_100_rollback_cycles(self):
        report = LongRunValidator().validate_100_rollback_cycles()
        assert report["iterations"] == 100
        assert report["status"] == "PASS", report["failures"]
