#!/usr/bin/env python3
"""Watch-only copy-trade replay engine.

Input is a normalized JSONL observation ledger. This program never connects to
an RPC, wallet, exchange, or signing provider; it only validates and replays
already-collected public observations.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED = {
    "observation_id", "asset_id", "chain", "source_tx", "observed_at",
    "block_time", "side", "quantity", "source_price_usd", "copy_price_usd",
    "copy_delay_seconds", "copy_fee_usd", "copy_slippage_bps",
}
SIDES = {"buy", "sell"}


def parse_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


def number(row: dict[str, Any], key: str) -> float:
    value = row[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return float(value)


def validate_row(row: dict[str, Any], line: int) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED - row.keys())
    if missing:
        errors.append(f"line {line}: missing {', '.join(missing)}")
        return errors
    if row["side"] not in SIDES:
        errors.append(f"line {line}: side must be buy or sell")
    for key in ("quantity", "source_price_usd", "copy_price_usd"):
        try:
            if number(row, key) <= 0:
                errors.append(f"line {line}: {key} must be > 0")
        except ValueError as exc:
            errors.append(f"line {line}: {exc}")
    for key in ("copy_delay_seconds", "copy_fee_usd", "copy_slippage_bps"):
        try:
            if number(row, key) < 0:
                errors.append(f"line {line}: {key} must be >= 0")
        except ValueError as exc:
            errors.append(f"line {line}: {exc}")
    if number(row, "copy_slippage_bps") >= 10000:
        errors.append(f"line {line}: copy_slippage_bps must be < 10000")
    try:
        block = parse_time(str(row["block_time"]))
        observed = parse_time(str(row["observed_at"]))
        delay = number(row, "copy_delay_seconds")
        if observed.timestamp() < block.timestamp():
            errors.append(f"line {line}: observed_at precedes block_time")
        if delay < 0:
            errors.append(f"line {line}: negative delay")
    except (TypeError, ValueError) as exc:
        errors.append(f"line {line}: invalid timestamp: {exc}")
    if not str(row["source_tx"]).strip():
        errors.append(f"line {line}: source_tx is required")
    return errors


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line, raw in enumerate(path.read_text().splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line}: invalid JSON: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"line {line}: expected JSON object")
            continue
        errors.extend(validate_row(row, line))
        rows.append(row)
    if errors:
        raise ValueError("\n".join(errors))
    seen: set[str] = set()
    for row in rows:
        if row["observation_id"] in seen:
            raise ValueError(f"duplicate observation_id: {row['observation_id']}")
        seen.add(row["observation_id"])
    rows.sort(key=lambda row: (parse_time(str(row["block_time"])), row["observation_id"]))
    return rows


@dataclass
class Position:
    quantity: float = 0.0
    cost_basis: float = 0.0


@dataclass
class Replay:
    cash: float
    initial_cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    fees: float = 0.0
    slippage_cost: float = 0.0
    fills: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    latest_prices: dict[str, float] = field(default_factory=dict)

    def apply(self, row: dict[str, Any], scale: float) -> None:
        asset = str(row["asset_id"])
        source_qty = number(row, "quantity")
        quantity = source_qty * scale
        source_price = number(row, "source_price_usd")
        copy_price = number(row, "copy_price_usd")
        slip_bps = number(row, "copy_slippage_bps")
        fee = number(row, "copy_fee_usd")
        direction = 1 if row["side"] == "buy" else -1
        fill_price = copy_price * (1 + direction * slip_bps / 10000)
        gross = quantity * fill_price
        position = self.positions.setdefault(asset, Position())
        self.latest_prices[asset] = fill_price
        if direction == 1:
            self.cash -= gross + fee
            position.quantity += quantity
            position.cost_basis += gross + fee
        else:
            if quantity > position.quantity + 1e-12:
                raise ValueError(f"cannot sell {quantity} {asset}; only {position.quantity} held")
            average_cost = position.cost_basis / position.quantity if position.quantity else 0.0
            proceeds = gross - fee
            self.cash += proceeds
            self.realized_pnl += proceeds - average_cost * quantity
            position.quantity -= quantity
            position.cost_basis -= average_cost * quantity
        self.fees += fee
        self.slippage_cost += quantity * abs(fill_price - copy_price)
        self.fills.append({
            "observation_id": row["observation_id"],
            "asset_id": asset,
            "side": row["side"],
            "quantity": quantity,
            "source_price_usd": source_price,
            "copy_price_usd": copy_price,
            "fill_price_usd": fill_price,
            "gross_usd": gross,
            "fee_usd": fee,
            "copy_delay_seconds": number(row, "copy_delay_seconds"),
            "source_tx": row["source_tx"],
        })
        self.equity_curve.append(self.cash + sum(p.quantity * self.latest_prices[a] for a, p in self.positions.items()))


def replay(rows: list[dict[str, Any]], initial_cash: float, scale: float) -> dict[str, Any]:
    if initial_cash <= 0 or scale <= 0:
        raise ValueError("initial_cash and scale must be > 0")
    state = Replay(cash=initial_cash, initial_cash=initial_cash)
    for row in rows:
        state.apply(row, scale)
    ending_marked = state.cash + sum(p.quantity * state.latest_prices[a] for a, p in state.positions.items())
    peak = state.initial_cash
    max_drawdown = 0.0
    for value in state.equity_curve:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / peak if peak else 0.0)
    return {
        "mode": "watch_only_replay",
        "execution": "none",
        "initial_cash_usd": state.initial_cash,
        "scale": scale,
        "observations": len(rows),
        "fills": state.fills,
        "ending_cash_usd": state.cash,
        "open_positions": {k: {"quantity": v.quantity, "cost_basis_usd": v.cost_basis, "last_mark_usd": state.latest_prices[k]} for k, v in state.positions.items() if v.quantity > 1e-12},
        "realized_pnl_usd": state.realized_pnl,
        "fees_usd": state.fees,
        "slippage_cost_usd": state.slippage_cost,
        "marked_equity_usd": ending_marked,
        "return_on_initial_cash": (ending_marked - state.initial_cash) / state.initial_cash,
        "max_marked_drawdown": max_drawdown,
        "limitations": [
            "Open positions are marked at the last observed copy fill, not a live market price.",
            "A replay is not evidence of future profitability.",
            "No wallet, exchange, RPC, or signing action occurred.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    val = sub.add_parser("validate")
    val.add_argument("input", type=Path)
    run = sub.add_parser("replay")
    run.add_argument("input", type=Path)
    run.add_argument("--initial-cash", type=float, default=100.0)
    run.add_argument("--scale", type=float, default=0.01, help="copy size as a fraction of observed quantity")
    run.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        rows = load_rows(args.input)
        if args.command == "validate":
            result = {"valid": True, "observations": len(rows), "assets": sorted({r["asset_id"] for r in rows})}
        else:
            result = replay(rows, args.initial_cash, args.scale)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if getattr(args, "output", None):
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
