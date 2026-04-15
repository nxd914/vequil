# Quant

Automated trading system on Kalshi (CFTC-regulated prediction markets).
Edge: crypto spot-price propagation latency between global CEX feeds (Binance/Coinbase) and Kalshi BTC/ETH probability contracts.

## Architecture

```
CryptoFeedAgent (Binance.US + Coinbase WS)
        ↓ tick_queue
FeatureAgent (Welford rolling windows)
        ↓ signal_queue (via features_to_signal)
        ↓ latest_features dict (shared)
WebSocket Agent ──price_cache──► Scanner Agent → Risk Agent → Execution Agent → SQLite audit trail
(Kalshi WS feed)                (BS N(d2) pricing) (Kelly+limits) (paper/live)
                                                                      ↓
                                                           Resolution Agent
                                                       (polls settlements, closes P&L)
```

Key packages: `agents/` (async agents) · `core/` (pure math + Kalshi client) · `tools/` (CLI, paper runner) · `research/` (analysis)

**Critical agents (all must be running):**
- `CryptoFeedAgent` — dual Binance/Coinbase WebSocket ingestion, emits `Tick` objects
- `FeatureAgent` — computes rolling features (returns, vol, momentum z-score) with dual windows (60s for signals, 15min for pricing), emits `Signal` objects
- `WebsocketAgent` — maintains real-time Kalshi price cache via WS
- `ScannerAgent` — matches crypto signals to Kalshi BTC/ETH contracts; threshold contracts priced via `spot_to_implied_prob` (N(d2)), bracket contracts via `bracket_prob` (N(d2_floor) − N(d2_cap)); vol floor `MIN_CRYPTO_VOL = 0.30`
- `RiskAgent` — gates trades with Kelly sizing, position limits, and proactive exposure-based circuit breaker
- `ExecutionAgent` — places paper/live orders, logs to SQLite with spot_price and signal_latency
- `ResolutionAgent` — resolves settled positions; **required** to free position slots (without it, trading halts after 5 positions)

## Invariants — never break these

1. `pricing.py` and `kelly.py` are pure math. Zero learned parameters in execution path.
2. Paper mode is default. `EXECUTION_MODE=live` requires explicit intent.
3. Every trade logs to SQLite with full audit trail (including spot_price_at_signal, signal_latency_ms).
4. Spread floor 4% minimum — Kalshi has no maker rebates, parabolic fee curve.
5. Kelly cap 0.25x. Max concurrent positions: 5. Max single exposure: 10% of bankroll. Daily loss gate: 20% of bankroll.
6. Kalshi taker fee (`0.07 × P × (1-P)` per contract) is factored into Kelly sizing and paper P&L. MIN_EDGE = 4% accounts for fee drag.
7. Max 4 hours to contract expiry (`MAX_HOURS_TO_CLOSE = 4`). Latency arb requires fast spot-to-probability convergence; far-dated contracts don't have it.
8. 30-second cooldown between fills (`MIN_SECONDS_BETWEEN_FILLS = 30`). Prevents burst-filling all 5 slots from a single signal cascade.
9. Max 2 positions per crypto symbol (`MAX_POSITIONS_PER_SYMBOL = 2`). Prevents concentration risk (e.g. all 5 slots on ETH brackets).
10. NO fill price floor 0.40 (`MIN_NO_FILL_PRICE = 0.40`). Below this, risk/reward inverts — risking $10k to win <$6.7k.
11. NO position size scales with fill price (`size = min(kelly_size, bankroll * 10% * no_price)`). Prevents flat $10k bets regardless of payout ratio.
12. ATM bracket skip: contracts where spot is within 0.5% of bracket midpoint are skipped (`MIN_BRACKET_DISTANCE_PCT = 0.005`). Model unreliable near ATM due to vol noise.
13. Bracket calibration haircut 45% (`BRACKET_CALIBRATION = 0.55`). N(d2) systematically overestimates narrow bracket probabilities due to discrete price jumps and CF Benchmark 60-second averaging.
14. Dual vol windows: 60-second for signal detection (jump/momentum), 15-minute for pricing (more stable for 1-4h contracts).
15. Trading hours window: scanner slows to 10-minute intervals outside 8:00-01:00 UTC (4 AM - 9 PM ET).
16. Resolution timeout: positions open longer than 6 hours are force-resolved as EXPIRED_TIMEOUT with conservative total-loss P&L.
17. Signal drain groups by symbol (`_signal_scan`). Burst signals for BTC and ETH arriving simultaneously are both processed — only the latest per symbol is kept, not a single global latest.
18. Daily P&L survives restarts. `ResolutionAgent._sync_risk_positions` rehydrates `RiskAgent._daily_pnl` from today's resolved trades in SQLite. Circuit breaker cannot be bypassed by crash+restart.
19. Circuit breaker is **proactive**: `RiskAgent._evaluate` rejects new trades if `daily_pnl - pending_pnl_at_risk - new_trade_max_loss < -MAX_DAILY_LOSS_PCT * bankroll`. `pending_pnl_at_risk` sums the max-loss exposure across all open positions. Prevents filling the 5th slot with exposure that could exceed the daily-loss gate before any position settles.

## Kalshi contract types

Kalshi crypto series (KXBTC, KXETH) offer two distinct event types:

| Type | `strike_type` | Ticker suffix | Example | Pricing |
|------|--------------|---------------|---------|---------|
| **Threshold** | `greater` / `less` | `-T` | "BTC above $74,400?" | `spot_to_implied_prob` → N(d2) |
| **Bracket** | `between` | `-B` | "BTC in $74,300–74,399.99?" | `bracket_prob` → N(d2\_floor) − N(d2\_cap) |

Both types are traded. `KalshiMarket` carries `floor_strike` and `cap_strike` (parsed from API). Bracket contracts require both fields; missing either is skipped with `SCORE skip bracket_no_strikes`.

Resolution source: **CF Benchmarks Real-Time Index** (60-second average before cutoff), not raw exchange spot.

## Kalshi API

- Base: `https://api.elections.kalshi.com/trade-api/v2`
- Auth: RSA-PSS. Env: `KALSHI_API_KEY` (UUID) + `KALSHI_PRIVATE_KEY_PATH` (PEM)
- V2 price fields: `yes_ask`/`yes_bid` in integer cents (1-99), divide by 100. Dollar fallbacks (`*_dollars` suffix) are already in [0.0, 1.0] — do NOT divide by 100 again.
- Bracket/threshold contracts expose `floor_strike` and `cap_strike` as floats in the raw JSON
- Volume: `volume_24h_fp` (fixed-point cents). Liquidity: `open_interest` -> `liquidity`
- Rate limits: 429 = exponential backoff. Never run two processes against same key.
- `strike_type` field on `/markets` response: `"greater"`, `"less"`, or `"between"`

## Environment

| Var | Required | Notes |
|-----|----------|-------|
| `KALSHI_API_KEY` | Yes | UUID from dashboard (stored in `.env`, never log) |
| `KALSHI_PRIVATE_KEY_PATH` | Yes | `~/.quant/kalshi_private.pem` |
| `EXECUTION_MODE` | No | `paper` (default) / `live` |
| `BANKROLL_USDC` | No | 100000 (both paper and live) |

## Process management

```bash
./scripts/run.sh start|stop|restart|status    # manages daemon.py (logs to data/)
python3 -m research.health_check              # P&L + process health
EXECUTION_MODE=paper python3 -m quant.daemon  # start autonomous paper loop
```

**Orphan daemon warning**: `run.sh` tracks a shell wrapper PID, not the Python process. On `restart`, kill any orphaned `python3 -m quant.daemon` processes manually (`ps aux | grep quant.daemon`). Running two daemons against the same Kalshi API key will cause rate-limit errors and duplicate orders.

## Current state

- **Phase**: Paper trading at $100k bankroll. Strategy overhaul 2026-04-15 after -$31k loss analysis; audit remediation 2026-04-15 (signal drain, P&L rehydration, proactive circuit breaker).
- **Edge**: Spot price delta (Binance.US + Coinbase) → Black-Scholes N(d2) → Kalshi BTC/ETH probability mispricing.
- **Goal**: 2+ weeks of paper data at Sharpe ≥ 1.0, then flip `EXECUTION_MODE=live`.
- **2026-04-14 scaling change**: Removed hardcoded dollar caps (`MAX_POSITION_SIZE_USDC`, `MAX_DAILY_LOSS_USDC`). All risk limits are percentage-based and scale with bankroll.
- **2026-04-15 strategy overhaul**: See strategy overhaul entry in known issues below. DB backed up to `data/paper_trades_v1_pre_strategy_fix.db`.
- **2026-04-15 audit fixes**: Signal drain race condition, daily P&L rehydration, proactive exposure circuit breaker. DB backed up to `data/paper_trades_v2_pre_audit_fixes.db`.

## Known issues & fixes

- **Bracket contracts not priced (fixed 2026-04-14)**: All active KXBTC/KXETH intraday markets are bracket contracts. Scanner was skipping them silently at DEBUG level, causing 0 trades. Fixed: `_score()` now branches on `_is_bracket_market()` and prices bracket contracts via `bracket_prob(spot, floor, cap, t, vol)` = N(d2_floor) − N(d2_cap). See `agents/scanner_agent.py:_score`, `core/pricing.py:bracket_prob`.

- **`_to_prob` double-divide bug (fixed 2026-04-14)**: `no_ask_dollars = "1.0000"` (=$1.00) was being treated as an integer cent value and divided by 100 → $0.01. This triggered max Kelly sizing on NO legs that were actually priced at certainty. Fixed: `*_dollars` fallback fields are direct decimal probabilities in [0.0, 1.0]; no `/100` applied. See `core/kalshi_client.py:_parse_market`.

- **Vol warmup cold-start (fixed 2026-04-14)**: After daemon restart, Welford rolling window is empty → `realized_vol ≈ 0` → ATM bracket probability collapses to ~1.0. Fixed: scanner skips contracts when `realized_vol <= 0.0` (warmup guard), then applies `MIN_CRYPTO_VOL = 0.30` floor for low-vol regimes. See `agents/scanner_agent.py:MIN_CRYPTO_VOL`.

- **`no_spot` on periodic scans (fixed 2026-04-14)**: First periodic scan fires before `_crypto_features` warms up, causing all contracts to be skipped. Fixed by adding `ScannerAgent._spot_cache` — populated from every signal that passes through `_signal_scan`. See `agents/scanner_agent.py:_get_spot_data`.

- **All 5 slots burst-filled on far-dated contracts (fixed 2026-04-14)**: Scanner had no max-expiry filter and risk agent had no burst protection. Three fixes: `MAX_HOURS_TO_CLOSE = 4` (scanner), `MIN_SECONDS_BETWEEN_FILLS = 30` (risk), `MAX_POSITIONS_PER_SYMBOL = 2` (risk). See `agents/scanner_agent.py`, `agents/risk_agent.py`.

- **P&L -$21.7k from bracket YES overexposure + stale signals (fixed 2026-04-14)**: YES bets were -$25.5k (1W/5L), NO bets were +$3.8k (5W/1L). Three fixes: `MAX_BRACKET_YES_PRICE = 0.30` (scanner), `BRACKET_CALIBRATION = 0.70` (pricing), `MAX_SIGNAL_AGE_SECONDS = 2.0` (risk). See `agents/scanner_agent.py`, `core/pricing.py`, `agents/risk_agent.py`.

- **Strategy overhaul after -$31k paper loss (fixed 2026-04-15)**: 17 trades in ~4 hours produced -$31,249 despite 75% win rate. All NO bets; 4 catastrophic ETH bracket losses (-$10.3k each) wiped out 12 small wins. Root causes and fixes:
  1. Flat $10k sizing on NO bets: Kelly computed 3-35% fractions but `MAX_SINGLE_EXPOSURE_PCT=0.10` capped everything at $10k. NO at $0.23 risked $10k to win $2.3k. Fixed: `MIN_NO_FILL_PRICE = 0.40` and NO position size now scales proportionally to fill price (`size *= no_price`).
  2. Near-ATM bracket mispricing: all 4 losses were ETH brackets where spot was within 0.5% of bracket midpoint. Model said 50-60%, market said 65-80%. Fixed: `MIN_BRACKET_DISTANCE_PCT = 0.005` skips near-ATM brackets.
  3. `BRACKET_CALIBRATION` lowered 0.70 → 0.55 (45% haircut). Model systematically overestimates bracket probs.
  4. 60-second vol window too noisy for pricing: added 15-minute `realized_vol_long` window for pricing; 60s retained for signal detection.
  5. Resolution agent silent: added heartbeat logs, timeout-based force-resolution for zombie positions (>6h).
  6. Trading hours window: scanner slows to 10-min intervals outside 08:00-01:00 UTC.
  See `agents/risk_agent.py:MIN_NO_FILL_PRICE`, `agents/scanner_agent.py:MIN_BRACKET_DISTANCE_PCT`, `core/pricing.py:BRACKET_CALIBRATION`, `core/features.py:VOL_WINDOW_LONG_SECONDS`, `agents/resolution_agent.py:MAX_OPEN_HOURS`.

- **Signal drain race condition (fixed 2026-04-15)**: `_signal_scan` drained burst signals keeping only the global latest. If BTC and ETH signals arrived simultaneously, one was silently dropped. Fixed: drain now groups by symbol using `latest_by_symbol` dict. See `agents/scanner_agent.py:_signal_scan`.

- **Circuit breaker bypass on restart (fixed 2026-04-15)**: `RiskAgent._daily_pnl` reset to $0 on process restart. Fixed: `ResolutionAgent._sync_risk_positions` now calls `_load_daily_pnl()` to rehydrate today's P&L from SQLite. See `agents/resolution_agent.py:_load_daily_pnl`.

- **Reactive circuit breaker (fixed 2026-04-15)**: `RiskAgent` previously only halted after `pnl_usdc` was realized from settled positions, so all 5 slots could fill with combined exposure exceeding the daily-loss gate before any resolved. Fixed: `_evaluate` now computes `pending_pnl_at_risk` = sum of max-loss exposure across `self._open_positions`, and rejects any new trade where `daily_pnl - pending_pnl_at_risk - new_trade_max_loss < -MAX_DAILY_LOSS_PCT * bankroll` with reason `PENDING_EXPOSURE_CAP`. See `agents/risk_agent.py:_evaluate`.

- **[DEFERRED] Math singularity in `pricing.d2` as t → 0**: Division by `math.sqrt(t)` for very small t yields extreme d2 values and model flip-flops in the final seconds of a contract. Recommended fix: apply a time-to-expiry floor (e.g. 60s) inside `core/pricing.py` or switch to linear decay in the final minute.

- **[DEFERRED] Audit trail does not log model parameters**: SQLite trade row records price/size/spot but not `realized_vol` used at the time of the decision. Add columns to the `paper_trades` schema so each row carries the vol/edge/kelly-fraction snapshot that produced the trade.

## Operational scripts

- `scripts/force_resolve.py` — Force-resolve stuck paper positions (marks as `EXPIRED_MANUAL` with `pnl_usdc=0.0`). Accepts optional ticker pattern filter. Interactive confirmation required.

## Live → Paper gate

Paper trading runs indefinitely until Sharpe ≥ 1.0 is demonstrated over 2+ weeks.
To go live: set `EXECUTION_MODE=live` in `.env` and restart. No code changes required.
