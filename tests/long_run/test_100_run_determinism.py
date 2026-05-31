"""
tests/long_run/test_100_run_determinism.py
"""

from __future__ import annotations

from src.certification import LongRunValidator


class Test100RunDeterminism:
    def test_100_consecutive_identical_fingerprints(self):
        report = LongRunValidator().validate_100_run_determinism()
        assert report["iterations"] == 100
        assert report["status"] == "PASS", report["failures"]
        assert report["invariant"] is True
