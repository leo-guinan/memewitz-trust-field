#!/usr/bin/env python3
"""Profile public callouts against a timestamped market observation ledger."""
from __future__ import annotations
import argparse, json, math
from datetime import datetime, timezone
from pathlib import Path


def time(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError(f"timestamp requires timezone: {s}")
    return d.astimezone(timezone.utc)


def num(row: dict, key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    if value <= 0:
        raise ValueError(f"{key} must be > 0")
    return float(value)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_no, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(row)
    return rows


def validate_callouts(rows: list[dict]) -> None:
    seen = set()
    for row in rows:
        for key in ("callout_id", "mint", "callout_time", "source_url", "status"):
            if not str(row.get(key, "")).strip():
                raise ValueError(f"callout missing {key}")
        if row["callout_id"] in seen:
            raise ValueError(f"duplicate callout_id: {row['callout_id']}")
        seen.add(row["callout_id"])
        time(row["callout_time"])
        if row["status"] not in {"verified", "partially_verified", "unknown"}:
            raise ValueError(f"invalid callout status: {row['status']}")


def validate_market(rows: list[dict]) -> None:
    for row in rows:
        for key in ("mint", "observed_at"):
            if not str(row.get(key, "")).strip():
                raise ValueError(f"market row missing {key}")
        time(row["observed_at"])
        num(row, "price_usd")
        if row.get("liquidity_usd") is not None:
            liquidity = row["liquidity_usd"]
            if isinstance(liquidity, bool) or not isinstance(liquidity, (int, float)) or liquidity < 0:
                raise ValueError("liquidity_usd must be >= 0 when present")


def evaluate(callouts: list[dict], market: list[dict], delays: list[int], windows: list[int]) -> list[dict]:
    by_mint: dict[str, list[dict]] = {}
    for row in market:
        by_mint.setdefault(row["mint"], []).append(row)
    for rows in by_mint.values():
        rows.sort(key=lambda row: time(row["observed_at"]))
    results = []
    for call in callouts:
        ctime = time(call["callout_time"])
        prices = by_mint.get(call["mint"], [])
        for delay in delays:
            eligible = [r for r in prices if (time(r["observed_at"]).timestamp() - ctime.timestamp()) >= delay]
            if not eligible:
                for window in windows:
                    results.append({"callout_id": call["callout_id"], "mint": call["mint"], "status": call["status"], "delay_seconds": delay, "window_minutes": window, "state": "no_entry_observation"})
                continue
            entry = eligible[0]
            entry_time = time(entry["observed_at"])
            entry_price = num(entry, "price_usd")
            for window in windows:
                end = entry_time.timestamp() + window * 60
                points = [r for r in prices if entry_time.timestamp() <= time(r["observed_at"]).timestamp() <= end]
                if not points:
                    results.append({"callout_id": call["callout_id"], "mint": call["mint"], "status": call["status"], "delay_seconds": delay, "window_minutes": window, "state": "no_window_observations"})
                    continue
                multiples = [num(r, "price_usd") / entry_price for r in points]
                peak = max(multiples)
                trough = min(multiples)
                final = multiples[-1]
                results.append({
                    "callout_id": call["callout_id"], "mint": call["mint"], "status": call["status"], "delay_seconds": delay, "window_minutes": window,
                    "state": "evaluated", "entry_observed_at": entry["observed_at"], "entry_price_usd": entry_price,
                    "peak_multiple": peak, "trough_multiple": trough, "end_multiple": final,
                    "peak_return": peak - 1, "max_drawdown_from_entry": 1 - trough,
                    "reached_2x": peak >= 2, "source_url": call["source_url"],
                })
    return results


def summarize(results: list[dict]) -> list[dict]:
    groups: dict[tuple[int, int], list[dict]] = {}
    for row in results:
        groups.setdefault((row["delay_seconds"], row["window_minutes"]), []).append(row)
    out = []
    for (delay, window), rows in sorted(groups.items()):
        evaluated = [r for r in rows if r["state"] == "evaluated"]
        peaks = sorted(r["peak_multiple"] for r in evaluated)
        out.append({
            "delay_seconds": delay, "window_minutes": window, "calls": len(rows), "evaluated": len(evaluated),
            "coverage": len(evaluated) / len(rows) if rows else 0,
            "two_x_hitrate_conditional": sum(r["reached_2x"] for r in evaluated) / len(evaluated) if evaluated else None,
            "median_peak_multiple": peaks[len(peaks) // 2] if peaks else None,
            "mean_peak_multiple": sum(peaks) / len(peaks) if peaks else None,
            "median_max_drawdown_from_entry": sorted(r["max_drawdown_from_entry"] for r in evaluated)[len(evaluated) // 2] if evaluated else None,
            "uncounted_states": {state: sum(r["state"] == state for r in rows) for state in {r["state"] for r in rows} if state != "evaluated"},
        })
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--callouts", type=Path, required=True)
    p.add_argument("--market", type=Path, required=True)
    p.add_argument("--delays", default="0,30,120,300,900")
    p.add_argument("--windows", default="5,15,60,360,1440")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    callouts, market = load_jsonl(args.callouts), load_jsonl(args.market)
    validate_callouts(callouts); validate_market(market)
    delays = [int(x) for x in args.delays.split(",") if x.strip()]
    windows = [int(x) for x in args.windows.split(",") if x.strip()]
    if any(x < 0 for x in delays) or any(x <= 0 for x in windows):
        raise ValueError("delays must be >= 0 and windows must be > 0")
    results = evaluate(callouts, market, delays, windows)
    report = {"mode": "watch_only_callout_profile", "execution": "none", "callouts": len(callouts), "market_rows": len(market), "delays_seconds": delays, "windows_minutes": windows, "summary": summarize(results), "results": results, "limitations": ["This measures price paths, not realized follower P&L.", "Peak multiples are retrospective and are not executable exit claims.", "Missing market observations remain uncovered, not zero-return calls.", "No transaction was submitted or signed."]}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"callouts": len(callouts), "market_rows": len(market), "evaluated_rows": sum(r["state"] == "evaluated" for r in results), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
