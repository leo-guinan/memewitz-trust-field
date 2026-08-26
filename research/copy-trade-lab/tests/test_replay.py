from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay import load_rows, replay


class ReplayTests(unittest.TestCase):
    def test_fixture_is_valid_and_round_trip_is_net_positive(self):
        rows = load_rows(ROOT / "fixtures" / "round_trip.jsonl")
        result = replay(rows, initial_cash=100.0, scale=0.1)
        self.assertEqual(result["observations"], 2)
        self.assertEqual(result["open_positions"], {})
        self.assertGreater(result["realized_pnl_usd"], 0)
        self.assertGreater(result["fees_usd"], 0)
        self.assertGreater(result["slippage_cost_usd"], 0)
        self.assertGreater(result["marked_equity_usd"], 100.0)

    def test_missing_source_transaction_is_rejected(self):
        path = ROOT / "fixtures" / "invalid_missing_tx.jsonl"
        path.write_text(json.dumps({"observation_id": "bad"}) + "\n")
        try:
            with self.assertRaises(ValueError):
                load_rows(path)
        finally:
            path.unlink(missing_ok=True)

    def test_oversized_sell_is_rejected(self):
        rows = load_rows(ROOT / "fixtures" / "round_trip.jsonl")
        rows[1]["quantity"] = 1000
        with self.assertRaises(ValueError):
            replay(rows, initial_cash=100.0, scale=0.1)


if __name__ == "__main__":
    unittest.main()
