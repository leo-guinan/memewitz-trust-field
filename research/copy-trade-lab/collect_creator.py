#!/usr/bin/env python3
"""Collect a bounded, watch-only creator transaction ledger from Solana RPC."""
from __future__ import annotations
import argparse, json, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

RPC_DEFAULT = "https://solana-rpc.publicnode.com"
CREATOR = "jmemehQbZXX7QqNE7Eyi81MdTZw6cEAT6TU4Kinwtru"
MINT = "3rbh7vzmyMgSmgssKHLn8iprVbsNgnWEj4h98hQhpump"
SOL = "So11111111111111111111111111111111111111112"


def rpc(url: str, method: str, params: list, request_id: int):
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "memewitz-watch-only-lab/1.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as response:
        result = json.load(response)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result.get("result")


def iso(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")


def delta_for_balance(balances: list[dict], owner: str, mint: str) -> tuple[int, int] | None:
    values = {b["accountIndex"]: int(b["uiTokenAmount"]["amount"]) for b in balances if b.get("owner") == owner and b.get("mint") == mint}
    if not values:
        return None
    # The creator should have one token account in this token's transaction.
    return next(iter(values.items()))


def collect(rpc_url: str, limit: int, sleep_seconds: float) -> tuple[list[dict], dict]:
    signatures = rpc(rpc_url, "getSignaturesForAddress", [CREATOR, {"limit": limit}], 1)
    rows: list[dict] = []
    scanned = 0
    for record in signatures:
        scanned += 1
        if record.get("err") is not None:
            continue
        tx = rpc(rpc_url, "getTransaction", [record["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}], scanned + 1)
        if not tx or tx.get("meta", {}).get("err") is not None:
            continue
        meta = tx["meta"]
        logs = meta.get("logMessages") or []
        if MINT not in json.dumps(tx) or not any("Instruction: Buy" in x or "Instruction: Sell" in x for x in logs):
            time.sleep(sleep_seconds)
            continue
        keys = tx["transaction"]["message"]["accountKeys"]
        wallet_index = next(i for i, key in enumerate(keys) if key.get("pubkey") == CREATOR)
        token_pre = delta_for_balance(meta.get("preTokenBalances", []), CREATOR, MINT)
        token_post = delta_for_balance(meta.get("postTokenBalances", []), CREATOR, MINT)
        if not token_pre or not token_post or token_pre[0] != token_post[0]:
            time.sleep(sleep_seconds)
            continue
        token_delta = token_post[1] - token_pre[1]
        if token_delta == 0:
            time.sleep(sleep_seconds)
            continue
        side = "buy" if token_delta > 0 else "sell"
        native_delta = meta["postBalances"][wallet_index] - meta["preBalances"][wallet_index]
        token_decimals = next(b["uiTokenAmount"]["decimals"] for b in meta.get("postTokenBalances", []) if b.get("owner") == CREATOR and b.get("mint") == MINT)
        token_quantity = abs(token_delta) / (10 ** token_decimals)
        quote_delta = -native_delta if side == "buy" else native_delta
        row = {
            "observation_id": f"solana:{record['signature']}:{MINT}",
            "source": "solana_rpc_getTransaction_jsonParsed",
            "chain": "solana",
            "wallet": CREATOR,
            "asset_id": f"solana:{MINT}",
            "mint": MINT,
            "quote_mint": SOL,
            "source_tx": record["signature"],
            "slot": tx.get("slot"),
            "finality": record.get("confirmationStatus"),
            "block_time": iso(tx["blockTime"]),
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "side": side,
            "quantity": token_quantity,
            "quantity_raw": abs(token_delta),
            "token_decimals": token_decimals,
            "wallet_quote_delta_lamports": quote_delta,
            "network_fee_lamports": meta.get("fee"),
            "source_price_quote_including_wallet_delta": quote_delta / (10 ** 9) / token_quantity,
            "copy_ready": False,
            "copy_ready_reason": "No delayed executable quote is present in this on-chain observation.",
            "instruction_logs": [x for x in logs if "Instruction:" in x],
        }
        rows.append(row)
        time.sleep(sleep_seconds)
    receipt = {
        "mode": "watch_only",
        "rpc": rpc_url,
        "wallet": CREATOR,
        "mint": MINT,
        "requested_signature_limit": limit,
        "signatures_scanned": scanned,
        "matching_observations": len(rows),
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "limitations": [
            "This is a bounded scan, not a complete wallet history.",
            "Wallet balance delta is not automatically an exact trade quote; it can include fees, rent, or unrelated movements.",
            "No delayed copy price is available, so observations are not replay-ready.",
            "No transaction was submitted or signed.",
        ],
    }
    return rows, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default=RPC_DEFAULT)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    rows, receipt = collect(args.rpc, args.limit, args.sleep)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
