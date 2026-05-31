"""
tests/long_run/test_full_recovery_cycles.py
"""

from __future__ import annotations

from src.certification import LongRunValidator


class TestFullRecoveryCycles:
    def test_100_recovery_cycles(self):
        report = LongRunValidator().validate_100_recovery_cycles()
        assert report["iterations"] == 100
        assert report["status"] == "PASS", report["failures"]
