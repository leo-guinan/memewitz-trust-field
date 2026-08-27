# Watch-only copy-trade lab

This is a research harness for testing whether a public trader's observable activity contains a reproducible signal. It is not a fund, broker, exchange, custody system, trading bot, or investment recommendation.

Identity status: the public Pump coin API links VIRUSEM mint `3rbh7...pump` to creator wallet `jmemeh...tru`. This is a public attribution for this experiment, not proof that the wallet controls any other wallet or token.

The first bounded public scan is now recorded in `observations.jsonl` with its
`collection-receipt.json`. It covers 200 recent creator-wallet signatures and
found two finalized VIRUSEM `BuyV2` observations. It found no sells in that
window. These rows are public-chain observations, not proof of profitability.

## What it does

`replay.py` validates and replays a normalized JSONL observation ledger with:

- exact chain and asset identifiers;
- public source transaction receipts;
- block time and observation time;
- source quantity and source price;
- delayed copy price;
- copy delay;
- copy fees;
- copy slippage;
- configurable copy-size scale;
- realized P&L, fees, slippage cost, open positions, and drawdown.

It never signs, submits, or routes a transaction.

## Run the synthetic fixture

```bash
python3 research/copy-trade-lab/replay.py validate \
  research/copy-trade-lab/fixtures/round_trip.jsonl

python3 research/copy-trade-lab/replay.py replay \
  research/copy-trade-lab/fixtures/round_trip.jsonl \
  --initial-cash 100 \
  --scale 0.1
```

The fixture exists to test mechanics only. Its positive result is not evidence about any real trader.

## Refresh a bounded public scan

```bash
python3 research/copy-trade-lab/collect_creator.py \
  --limit 200 --sleep 1 \
  --output research/copy-trade-lab/observations.jsonl \
  --receipt research/copy-trade-lab/collection-receipt.json
```

The collector uses a public Solana RPC and only writes finalized transactions
that contain the verified mint and a Pump buy/sell instruction. It records the
creator wallet, mint, transaction signature, block time, token delta, native
balance delta, and explicit limitations. It does not submit transactions.

The observation ledger is deliberately separate from replay input: on-chain
events do not automatically provide the delayed executable copy price required
for a fair replay.

## Profile recovered callouts across windows

`profile_callouts.py` compares a recovered callout stream with timestamped
market observations. It evaluates 0s/30s/2m/5m/15m entry delays against
5m/15m/1h/6h/24h windows by default:

```bash
python3 research/copy-trade-lab/profile_callouts.py \
  --callouts research/copy-trade-lab/fixtures/callouts.jsonl \
  --market research/copy-trade-lab/fixtures/market.jsonl \
  --output /tmp/callout-profile.json
```

Callout rows require `callout_id`, exact `mint`, timezone-aware
`callout_time`, source URL, and a status of `verified`, `partially_verified`,
or `unknown`. Market rows require exact `mint`, timestamp, and `price_usd`.
The evaluator reports coverage separately from conditional 2x hit rate. A
missing price observation is `no_entry_observation` or
`no_window_observations`, never a zero-return call. Peak multiples are
retrospective path statistics, not executable profit claims.

## Observation contract

Every JSONL row must contain:

```text
observation_id
asset_id                  # chain-qualified identity, not a ticker alone
chain
source_tx                 # public receipt; no inferred identity
observed_at               # when our system could observe it
block_time                # source event time
side                      # buy or sell
quantity
source_price_usd
copy_price_usd            # executable price after observation delay
copy_delay_seconds
copy_fee_usd
copy_slippage_bps
```

The ingestion layer must preserve provider, endpoint, retrieval timestamp, and failure status in the surrounding run receipt. A missing provider response is not an empty market and should never be zero-filled.

## Research sequence

1. Resolve the exact public wallet and token identity independently.
2. Collect public transactions into an append-only ledger.
3. Validate the ledger; reject duplicates, missing receipts, timestamp inversions, and sells without inventory.
4. Freeze a strategy rule and observation delay.
5. Replay on an initial sample.
6. Evaluate held-out future observations without changing the rule.
7. Compare against buy-and-hold, random entry, delayed momentum, and no-trade baselines.
8. Report net results after fees, slippage, delay, failed or uncopyable events, and open inventory.

## Falsifiers

The copy hypothesis is weakened or rejected if:

- apparent profit disappears after delay and slippage;
- results do not beat a no-trade or simple baseline out of sample;
- only unrealized gains explain the result;
- the strategy depends on transactions that cannot be observed before the price moves;
- the wallet's activity is mixed with transfers, allocations, or multiple uncontrolled wallets;
- a small test works only because the simulated order changes no liquidity, while real execution would move the market;
- losses, skipped trades, and failed reads are absent from the ledger.

## Boundaries

Do not add private keys, seed phrases, exchange credentials, balances, cost basis, donor identities, or private raw payloads. Do not turn this into pooled capital or automatic execution without separate legal, compliance, custody, and user-approval work.
