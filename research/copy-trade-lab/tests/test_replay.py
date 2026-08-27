from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay import load_rows, replay
from profile_callouts import evaluate, load_jsonl, summarize, validate_callouts, validate_market


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

    def test_callout_windows_preserve_missing_coverage(self):
        calls = load_jsonl(ROOT / "fixtures/callouts.jsonl")
        market = load_jsonl(ROOT / "fixtures/market.jsonl")
        validate_callouts(calls)
        validate_market(market)
        rows = evaluate(calls, market, [0, 300], [5, 15])
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(r["state"] == "evaluated" for r in rows), 4)
        self.assertEqual(sum(r["state"] == "no_entry_observation" for r in rows), 4)
        summary = summarize(rows)
        zero_delay = next(r for r in summary if r["delay_seconds"] == 0 and r["window_minutes"] == 5)
        self.assertEqual(zero_delay["coverage"], 0.5)
        self.assertEqual(zero_delay["two_x_hitrate_conditional"], 1.0)

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
