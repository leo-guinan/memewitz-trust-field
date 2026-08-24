#!/usr/bin/env python3
"""Run the public-safe Memewitz GTM search over an exported NDJSON corpus."""
from __future__ import annotations
import argparse, json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "MEMEWITZ_GTM_SEARCH.yaml"
OUTPUT = ROOT / "search-results.json"

LANES = {
    "market_problem": ["dex", "bots", "scam", "drained", "trust", "migration"],
    "audience": ["holders", "community", "traders", "beginners", "solana", "bot"],
    "proof_artifacts": ["locked", "burn", "wallet", "on-chain", "gmgn", "streamflow", "strategy", "results"],
    "offer": ["analysis", "checklist", "report", "strategy", "callout", "before buying"],
    "distribution": ["thread", "post", "content", "callout", "community", "twitter"],
    "conversion": ["reply", "feedback", "contribute", "join", "submit", "follow"],
    "falsifiers": ["failed", "loss", "dump", "mistake", "scam", "correction"],
}

def load_rows(path: Path):
    rows=[]
    for line in path.read_text(errors="replace").splitlines():
        try:
            row=json.loads(line)
        except json.JSONDecodeError:
            continue
        tweet=row.get("tweet") or {}
        if tweet.get("text"):
            rows.append(tweet)
    return rows

def hit(tweet, term):
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])", tweet.get("text", ""), re.I) is not None

def score(tweet, current_cutoff="2026-07-25"):
    m=tweet.get("metrics") or {}
    s=sum(int(m.get(k,0) or 0) for k in ("likes_visible","replies_visible","reposts_visible"))
    if tweet.get("author_handle") == "itzmemewitz": s += 2
    if (tweet.get("created_at") or "") >= current_cutoff: s += 2
    return s

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="path to the exported NDJSON corpus")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="search receipt path")
    args=parser.parse_args()
    source=args.source.expanduser().resolve()
    output=args.output.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"source missing: {source}")
    rows=load_rows(source)
    own=[r for r in rows if r.get("author_handle") == "itzmemewitz"]
    lanes={}
    for name,terms in LANES.items():
        hits=[]
        for row in own:
            matched=[term for term in terms if hit(row,term)]
            if matched:
                hits.append({"tweet_id":row.get("tweet_id"),"created_at":row.get("created_at"),"terms":matched,"score":score(row)})
        lanes[name]={"terms":terms,"count":len(hits),"top_hits":sorted(hits,key=lambda x:x["score"],reverse=True)[:15]}
    out={
        "search_id":"memewitz-dex-gtm-2026-08-24",
        "source":"local NDJSON export; visible surface only",
        "corpus":{"rows":len(rows),"operator_rows":len(own),"other_visible_authors":len({r.get('author_handle') for r in rows if r.get('author_handle') != 'itzmemewitz'})},
        "term_frequency":Counter(term for terms in LANES.values() for term in terms for row in own if hit(row,term)),
        "lanes":lanes,
        "privacy":{"raw_actor_credentials_excluded":True,"private_balances_excluded":True,"wallet_addresses_not_copied":True},
    }
    out["term_frequency"]=dict(out["term_frequency"])
    output.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"output":str(output),"rows":len(rows),"operator_rows":len(own),"lane_counts":{k:v["count"] for k,v in lanes.items()}},indent=2))

if __name__ == "__main__": main()
