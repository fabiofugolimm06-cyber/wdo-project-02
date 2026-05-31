"""
tests/long_run/test_100_snapshot_replays.py
"""

from __future__ import annotations

from src.certification import LongRunValidator


class Test100SnapshotReplays:
    def test_100_snapshot_replays_invariant(self):
        report = LongRunValidator().validate_100_snapshot_replays()
        assert report["iterations"] == 100
        assert report["status"] == "PASS", report["failures"]
