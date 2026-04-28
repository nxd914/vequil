# Kinzie — Comprehensive Audit & Actionable Roadmap

**Date:** 2026-04-28  
**Scope:** Full-stack review of strategy, model, infrastructure, operations, compliance, and business strategy for a firm targeting institutional-grade proprietary trading status.  
**Current state:** Paper-trading only. 8 resolved fills. Single-asset-class (BTC/ETH crypto binary contracts on Kalshi). One active deployment. No live capital at risk.

---

## Scoring Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 | Critical — blocks live trading or creates material financial/legal risk |
| 🟡 | High — limits scale, edge, or resilience significantly |
| 🟢 | Medium — meaningful improvement but not urgent |

---

## Part 1 — Model & Strategy

### 1.1 🔴 BRACKET_CALIBRATION tuned from a single data point

**Finding:** `BRACKET_CALIBRATION = 0.55` was set after one losing paper trade (model: 0.81, market: 0.51). The docs acknowledge this explicitly but the code treats it as production-grade. One observation cannot distinguish model error from bad luck.

**Risk:** If the true calibration factor is 0.70–0.80 (the original value), then the current haircut causes the system to systematically *underprice* brackets, missing real edge. If 0.55 is too high, the system still enters losing bracket trades.

**Actions:**
- [ ] Log `model_prob` into `_OpenRow` so the resolution agent can compute per-fill calibration error (currently stored as sentinel `-1.0`).
- [ ] Do not adjust `BRACKET_CALIBRATION` again until ≥50 bracket fills are logged with `(model_prob, won)` pairs.
- [ ] Build a calibration regression: `realized_win_rate = f(model_prob)` per contract type. Any slope ≠ 1 or intercept ≠ 0 indicates systematic miscalibration.
- [ ] Add separate calibration constants for short (< 1h), medium (1–2h), and long (2–4h) time horizons — the model may behave differently across these regimes.

---

### 1.2 🔴 CF Benchmarks basis risk is unmodeled

**Finding:** Kalshi crypto contracts settle against the CF Benchmarks Real-Time Index (60-second TWAP). The system prices against raw Binance.US / Coinbase spot. On fast markets this basis can be 1–2%; on normal days 0.1–0.5%. For contracts near-the-money this basis directly creates entry error that is treated as "irreducible noise" in `docs/CALIBRATION.md`.

**Risk:** A systematic positive basis (Binance spot > CF TWAP) would cause the model to chronically overestimate YES probabilities for above-strike contracts, generating repeated losses on momentum-up signals that move spot but not the settlement index.

**Actions:**
- [ ] Subscribe to the CF Benchmarks Real-Time Index API (free tier available) and use its published price as the spot input for the pricing model — not raw exchange feed.
- [ ] Until that feed is available, add a basis correction factor to `spot_to_implied_prob()` as a config parameter (`cf_basis_adjustment: float = 0.0`, default neutral). Tune from fills.
- [ ] Log CF index price (if available) at signal time so basis can be measured retroactively.

---

### 1.3 🔴 Taker-only execution permanently caps edge

**Finding:** The system is taker-only — every fill pays the full bid-ask spread plus the Kalshi taker fee (max 1.75% at P=0.50). The 4% minimum edge floor accounts for this, but maker limit orders would reduce cost by ~2–3% per trade, lowering the minimum viable edge and dramatically expanding the opportunity set.

**Risk:** Taker-only means the system passes on all markets with edge between 2–4%, which at scale could represent the majority of mispricing events (Kalshi spreads narrow as liquidity grows).

**Actions:**
- [ ] Implement limit order capability in `ExecutionAgent._live_order()` using Kalshi's REST order API with a `limit` order type at the mid-price.
- [ ] Add a `use_limit_orders: bool = False` config flag and test in paper mode by simulating limit fills only when the ask crosses the bid.
- [ ] Add a fill rate tracker: what percentage of limit orders placed at mid actually fill within the signal age window (2s). If fill rate is below 50%, fall back to market orders.
- [ ] Once limit orders are implemented, lower `MIN_EDGE` threshold experimentally from 4% to 2% and measure edge degradation.

---

### 1.4 🟡 Flat volatility surface — no term structure or smile

**Finding:** The pricing model uses a single realized vol estimate (15-minute Welford window) for all contracts regardless of time to expiry (5 minutes to 4 hours). In reality, volatility is not constant across horizons — short-dated contracts should use realized vol over a comparable window, not the same 15-minute estimate used for 4-hour contracts.

**Risk:** For 5-minute contracts, 15-minute vol dramatically overstates the uncertainty horizon and may systematically price YES above fair value near strikes. For 4-hour contracts, 15-minute vol is too short a lookback and will overreact to transient vol spikes.

**Actions:**
- [ ] Implement a vol term structure: use 5-minute realized vol for contracts < 30 min to expiry, 15-minute vol for 30–90 min, 60-minute vol for 90+ min. Add all three windows to `FeatureVector` and `RollingWindow`.
- [ ] Backtest this change against existing fill history before deploying.
- [ ] Consider a GARCH(1,1) overlay: crypto vol is autocorrelated, and a GARCH forecast outperforms realized vol rolling windows on 1–4 hour horizons in every published academic comparison.

---

### 1.5 🟡 No regime detection — same parameters in all market conditions

**Finding:** `config.py` has one set of thresholds for all market regimes (trending, mean-reverting, low-vol, crisis). The `min_crypto_vol` floor of 0.30 filters out low-vol regimes, but the system uses the same `min_edge`, `kelly_fraction_cap`, and `momentum_z_threshold` in both a 0.30 vol environment and a 2.0 vol crisis environment.

**Risk:** During high-vol regimes (BTC ±10% days), the log-normal model breaks down (jump dynamics dominate), spreads widen, and the system may generate a burst of signals from momentum z-scores with poor edge quality. During trending regimes, latency arb signals may be systematically biased in one direction.

**Actions:**
- [ ] Add a `vol_regime` classifier (low: vol < 0.50, normal: 0.50–1.0, high: > 1.0) based on the 60-minute realized vol.
- [ ] In high-vol regimes: raise `min_edge` to 0.08, lower `kelly_fraction_cap` to 0.15, and restrict to threshold contracts only (no brackets).
- [ ] In low-vol regimes: extend `max_hours_to_close` to 6 hours (convergence is slower) and lower `momentum_z_threshold` to 1.5 (smaller moves carry more information).
- [ ] Log the active regime with every trade for post-hoc attribution analysis.

---

### 1.6 🟡 Sharpe annualization assumes 4 fills/day — not data-driven

**Finding:** `ResolutionAgent._running_sharpe()` annualizes using `math.sqrt(assumed_fills_per_day * 365)`, where `assumed_fills_per_day = 4` is a hardcoded guess. With 8 fills over an unknown period, the true cadence is unknown. An incorrect annualization factor produces a Sharpe estimate that is meaningless for the live-mode gate.

**Actions:**
- [ ] Compute actual fill cadence from `placed_at` timestamps in the DB rather than an assumed value. Store the first-fill timestamp at startup and divide total fills by elapsed days.
- [ ] Use time-series Sharpe (P&L per hour) rather than per-fill Sharpe for more robust estimation at low N.
- [ ] The `min_fills_for_live` gate of 100 is appropriate; raise `min_sharpe_for_live` to 1.5 to account for the inflated Sharpe from a too-small sample.

---

### 1.7 🟢 Signal confidence function is arbitrary

**Finding:** `confidence = min(0.95, 0.55 + 0.05 × (z - 2.0))`. This formula is not derived from any empirical relationship between z-score magnitude and subsequent edge. It is a linear heuristic that increases confidence by 5% for every additional sigma above the threshold, capping at 0.95. Confidence is not used in sizing (Kelly is used), but it gates signal propagation.

**Actions:**
- [ ] Log z-score and subsequent contract mispricing edge for every signal (hit or miss). After 200 signals, fit a logistic regression of `edge > 0.04` on z-score to produce a calibrated confidence score.
- [ ] Until then, document explicitly that `confidence` is a placeholder and not a calibrated probability.

---

### 1.8 🟢 Only two assets — extreme concentration risk for a prop firm

**Finding:** The system trades BTC and ETH contracts on Kalshi exclusively. These two assets have a 30-day correlation of ~0.85, meaning nearly all open positions are exposed to the same underlying factor.

**Actions:**
- [ ] Expand to all liquid Kalshi crypto contracts: SOL, XRP, DOGE, BNBUSDT as they become available.
- [ ] Add non-crypto Kalshi markets: Fed Funds rate, CPI, unemployment — these are uncorrelated with crypto and expand the opportunity set significantly.
- [ ] Research Polymarket, Manifold, and PredictIt for additional venues (regulatory caution applies to the latter).
- [ ] In the long run, build a cross-asset Kelly portfolio optimizer that accounts for pairwise correlation when sizing concurrent positions.

---

## Part 2 — Infrastructure & Operations

### 2.1 🔴 SQLite in production with no backup automation

**Finding:** All trade data, position state, and audit trail lives in `data/paper_trades.db` — a single file with no replication, no WAL mode confirmed, and no automated backup. The runbook says "backup manually." If the host disk fails or the file is corrupted, the entire history and any live position state is lost.

**Actions:**
- [ ] Enable WAL mode: `conn.execute("PRAGMA journal_mode=WAL")` in `_init_db()` to prevent read/write locking issues with the concurrent resolution agent.
- [ ] Add automated daily backup to object storage (S3/R2/GCS) with a 30-day retention policy. Add this to `scripts/run.sh`.
- [ ] Migrate to PostgreSQL before live trading. SQLite's write serialization will become a bottleneck when resolution and execution are writing concurrently at higher fill rates.
- [ ] Add DB integrity check on startup: `PRAGMA integrity_check`.

---

### 2.2 🔴 No alerting or on-call notification

**Finding:** The system logs to a local file. There is no mechanism to notify operators when a circuit breaker fires, a feed goes down for >10 minutes, an unhandled exception occurs, or a position gets stuck. The runbook says to watch the log manually.

**Risk:** A feed disconnect at 3am is not discovered until the operator checks the log the next morning. A Kalshi API outage silently prevents resolutions, blocking all position slots. A stuck position permanently halts trading.

**Actions:**
- [ ] Integrate a notification channel (Slack webhook, PagerDuty, or SMS via Twilio) for the following events: circuit breaker fires, feed down > 5 minutes, stuck position > MAX_OPEN_HOURS, unhandled exception in any agent, daily loss > 10% (warning, pre-circuit-breaker).
- [ ] Add a `/health` HTTP endpoint (already has FastAPI as a dependency) that external uptime monitors (BetterUptime, UptimeRobot) can poll every 60 seconds.
- [ ] Add process-level supervision: use Railway's built-in restart policy or `supervisord` to restart the daemon if it crashes (currently no crash recovery mechanism exists).

---

### 2.3 🔴 Bankroll is hardcoded — no live capital management

**Finding:** `BANKROLL_USDC` is read from an env var at startup and never updated. If live positions win or lose, the Kelly sizing continues to use the original bankroll figure rather than the current account balance. Over time this causes Kelly fractions to diverge from optimal: overbetting after losses, underbetting after gains.

**Actions:**
- [ ] Add a `_current_bankroll()` method to `RiskAgent` that returns `_bankroll + _daily_pnl + sum(pending_position_values)`. Use this in `_evaluate()` instead of the static `self._bankroll`.
- [ ] In live mode, query the Kalshi API for the actual account USDC balance on startup and after each resolution, and update `_bankroll` accordingly.
- [ ] Store the bankroll snapshot to SQLite daily so it survives restarts.

---

### 2.4 🟡 Single point of failure in the market data pipeline

**Finding:** The `CryptoFeedAgent` connects to Binance.US and Coinbase. If both go offline simultaneously (not rare — both have had correlated outages during high-volatility events), the feature pipeline starves and no signals fire. The agent reconnects but cannot detect that it has been receiving stale cached data from the `WebsocketAgent` for Kalshi prices without also knowing the CEX feed is stale.

**Actions:**
- [ ] Add a "data freshness" guard in `ScannerAgent`: reject any opportunity where the most recent CEX tick for the relevant symbol is older than `max_feed_age_seconds` (recommended: 10 seconds).
- [ ] Add a third CEX feed (Kraken or OKX) as a hot-standby. If the primary feeds drop, switch to the fallback automatically.
- [ ] Add a `last_tick_at` timestamp per symbol to `FeatureAgent.latest_features` and check it in `RiskAgent._evaluate()`.

---

### 2.5 🟡 No co-location or latency measurement to Kalshi

**Finding:** The latency arb thesis depends on being faster than other market participants repricing Kalshi contracts after a CEX move. The system has never measured its actual round-trip latency to Kalshi's API servers, nor is there any co-location strategy. The current deployment on Railway (shared cloud) has non-deterministic network latency.

**Risk:** Other participants with co-located infrastructure or direct market data connections may be faster, capturing the mispricing window before this system can act.

**Actions:**
- [ ] Add latency measurement to every Kalshi API call and log `p50`, `p95`, `p99` latency to the Kalshi endpoint daily.
- [ ] Measure the actual Kalshi repricing delay empirically: when CEX spot moves by > 0.5%, how many seconds until the Kalshi WebSocket sends a price update? This is the arb window — if it's < 1s, the current 2-second signal age gate may already be too slow.
- [ ] Deploy to a server with the lowest latency path to Kalshi's infrastructure (likely AWS us-east-1 based on Kalshi's East Coast presence). Compare Railway vs bare metal VPS.

---

### 2.6 🟡 No parameter optimization pipeline

**Finding:** All thresholds in `config.py` (min_edge, kelly_fraction_cap, momentum_z_threshold, etc.) were set by domain reasoning, not empirical optimization. There is no systematic process to test whether different parameter values improve Sharpe, and no protection against overfitting such a process.

**Actions:**
- [ ] Build a grid-search backtester on top of `research/replay_backtest.py` that sweeps key parameters (min_edge, momentum_z_threshold, vol windows) and reports out-of-sample Sharpe for each configuration.
- [ ] Use walk-forward optimization (train on first 60% of fills, test on last 40%) to prevent overfitting.
- [ ] Never optimize parameters in-sample on the live fill history without an explicit holdout set.

---

### 2.7 🟢 Log aggregation is file-only

**Finding:** Logs rotate at 10 MB with 5 files kept, meaning roughly 50 MB of history. At higher fill rates or verbose DEBUG logging, this may not cover even 24 hours of operation.

**Actions:**
- [ ] Ship logs to a log aggregation service (Datadog, Loki/Grafana, CloudWatch). The `LOG_FORMAT=json` structured logging support already exists — just needs a shipper.
- [ ] Build a metrics dashboard: fill rate per hour, edge distribution histogram, win rate rolling 24h, Sharpe rolling 7-day, agent queue depths. This is more actionable than raw logs for operational oversight.

---

### 2.8 🟢 No A/B testing framework for model variants

**Finding:** When changing pricing parameters (e.g., `BRACKET_CALIBRATION`), the entire system switches at once. There is no way to run two model variants simultaneously and compare performance.

**Actions:**
- [ ] Add a `model_variant` tag to every trade record in SQLite.
- [ ] Support running two `ScannerAgent` instances with different configs, each writing tagged trades, so model variants can be compared on the same market opportunities.

---

## Part 3 — Live Trading Readiness

### 3.1 🔴 Live order placement is `NotImplementedError`

**Finding:** `ExecutionAgent._live_order()` raises `NotImplementedError`. The live execution path has never been written. The `KalshiClient` has the API authentication plumbing, but no `place_order()` method is exposed.

**Actions:**
- [ ] Implement `KalshiClient.place_order(ticker, side, price, num_contracts)` using the Kalshi REST API `POST /trade-api/v2/portfolio/orders`.
- [ ] Implement order status polling: `KalshiClient.get_order(order_id)` to confirm fill.
- [ ] Handle partial fills: if only some contracts fill, record the actual filled quantity and price — not the requested size.
- [ ] Implement order cancellation: `KalshiClient.cancel_order(order_id)` for the case where a limit order doesn't fill within the signal window.
- [ ] Test the full live path in paper mode by mocking the Kalshi client with a real sandbox/staging environment if Kalshi provides one.

---

### 3.2 🔴 8 fills is not a sample size — live gate must hold

**Finding:** 8 fills provide no statistical power. At a 65% win rate, the 95% confidence interval on win rate with n=8 is [0.30, 0.90]. The live-mode gate at 100 fills / Sharpe ≥ 1.0 is correct and must not be bypassed.

**Actions:**
- [ ] Do not touch `min_fills_for_live = 100`. Raise it to 200 for higher statistical confidence.
- [ ] Add a mandatory 2-week continuous paper trading window check in addition to the fill count: `min_paper_trading_days: int = 14`. This guards against gaming the fill count with artificial high-frequency activity.
- [ ] Track paper trading start date in the DB and enforce this in the live-mode gate.

---

### 3.3 🟡 No slippage model in paper mode

**Finding:** `_paper_order()` fills at the current `yes_ask` with zero slippage. In live markets, large orders move prices, and at thin Kalshi order book depths, even $500 orders may consume multiple price levels.

**Risk:** Paper Sharpe will be systematically optimistic relative to live performance if market impact is non-trivial.

**Actions:**
- [ ] Add a configurable slippage model to paper fills: `fill_price = ask × (1 + slippage_factor)`, where `slippage_factor` is calibrated from the Kalshi order book depth (available via the `liquidity` field on `KalshiMarket`).
- [ ] Use a square-root market impact model: `slippage = k × sqrt(size_usdc / liquidity)`. Calibrate `k` from live fills once live trading begins.

---

### 3.4 🟡 No limit on total capital deployed across the firm

**Finding:** `max_single_exposure_pct = 0.10` and `max_concurrent_positions = 5` cap individual and portfolio positions, but there is no check on total deployed capital as a fraction of the Kalshi market's total open interest. Deploying $50k into a market with $20k total open interest is not possible and not guarded.

**Actions:**
- [ ] Add a `max_position_as_pct_of_oi: float = 0.15` config parameter. Before any fill, compute `size_usdc / market.open_interest_usdc` and reject if above threshold.
- [ ] Track the `volume_24h` field on `KalshiMarket` and skip any market where the proposed size exceeds 10% of daily volume.

---

## Part 4 — Compliance & Legal

### 4.1 🔴 Regulatory status of the trading entity is undefined

**Finding:** The system trades on Kalshi, a CFTC-designated contract market (DCM). Kalshi is legal in the US, but operating as a proprietary trading firm — especially one intending to be "one of the biggest in the world" — requires attention to regulatory classification.

**Actions:**
- [ ] Consult a commodities/derivatives attorney to determine if trading on Kalshi at scale triggers CFTC registration requirements (commodity trading advisor, commodity pool operator, etc.).
- [ ] Incorporate the trading entity as an LLC or LP with a clear operating agreement before deploying live capital. This limits personal liability and enables proper bookkeeping.
- [ ] Review Kalshi's Terms of Service to confirm automated trading is explicitly permitted and that there are no volume or position limits that apply to API traders.
- [ ] Establish a formal AML/KYC policy even for internal operations — required if external capital is ever accepted.

---

### 4.2 🔴 No tax accounting infrastructure

**Finding:** Every trade generates a taxable event (short-term capital gain/loss in the US). With automated trading at the cadence this system targets, tax records need to be computed accurately across hundreds of fills per year.

**Actions:**
- [ ] Integrate with a crypto/prediction market tax tool (TaxBit, Koinly, or a custom export) from day one of live trading.
- [ ] Add a `tax_lot_id` column to the trades table to support FIFO/LIFO lot matching.
- [ ] Generate quarterly estimated tax calculations from the SQLite audit trail.
- [ ] Open a separate brokerage or bank account for the trading entity to keep personal and business finances separated.

---

### 4.3 🟡 Market manipulation risk is unaddressed

**Finding:** Prediction market contracts on binary outcomes can theoretically be moved by market participants placing large orders. The system does not include any detection of manipulation in the markets it trades, and its own trading (if large enough) could constitute manipulation if it moves a thinly-traded Kalshi market in a direction that benefits other positions.

**Actions:**
- [ ] Add a manipulation detection filter in `ScannerAgent`: skip any market where the bid-ask spread moved by > 20% in the last 60 seconds without a corresponding spot move (potential wash trading or spoofing).
- [ ] Cap order size at `min(size_usdc, 0.10 × market.volume_24h)` to prevent the system from being a dominant participant in any single market.
- [ ] Review Kalshi's surveillance rules and ensure the trading strategy does not trigger any wash trading or spoofing detections.

---

### 4.4 🟢 API key security practices

**Finding:** The `KALSHI_PRIVATE_KEY_PATH` stores an RSA-2048 private key in a filesystem path. The key is never rotated (no procedure exists) and the runbook path example (`~/.latency/private.pem`) is in the home directory with no file permission guidance.

**Actions:**
- [ ] Document that the private key file must be `chmod 600` and owned by the daemon user only.
- [ ] Add a key rotation procedure to the RUNBOOK.md: generate a new keypair, upload the new public key to Kalshi, update the env var, restart the daemon.
- [ ] Consider storing the private key in a secrets manager (AWS Secrets Manager, HashiCorp Vault, Railway's secret store) rather than a filesystem path.
- [ ] Add startup validation: if `KALSHI_PRIVATE_KEY_PATH` points to a file with permissions > 600, log a warning.

---

## Part 5 — Business Strategy (Path to Institutional Scale)

### 5.1 🔴 No track record documentation

**Finding:** A prop firm's primary asset is its audited track record. The current paper trade history in SQLite is the only record and it has no external validation. To attract talent, raise capital, or establish credibility, a verified track record is essential.

**Actions:**
- [ ] At 100 fills, export the full trade history and have a third-party auditor (accounting firm or trading technology auditor) verify the SQLite records against Kalshi's settlement history.
- [ ] From the first live trade, use a fund administrator or prime broker that provides independent position verification.
- [ ] Document monthly P&L, Sharpe, max drawdown, and win rate in a standardized format (GIPS compliance if pursuing institutional capital).

---

### 5.2 🔴 Single strategy, single venue, single asset class

**Finding:** The entire firm is one strategy (latency arb) on one venue (Kalshi) on two assets (BTC, ETH). If Kalshi changes its fee schedule, modifies its API, or Kalshi's crypto markets see more efficient participants, the entire revenue stream disappears.

**Actions:**
- [ ] **Expand market universe immediately:** Fed Funds rate contracts, CPI, NFP, and other Kalshi macro contracts have lower participant sophistication and potentially higher edge.
- [ ] **Research Polymarket:** Decentralized prediction market with higher open interest in some categories. Regulatory status varies by jurisdiction — US access requires careful legal review.
- [ ] **Build a second strategy:** Mean-reversion or market-making on Kalshi (provide liquidity instead of taking it) would earn the spread rather than pay it, and hedges taker-only exposure.
- [ ] **Research options on BTC/ETH:** If the realized-vol model is accurate, there may be parallel edge in CME Bitcoin options or Deribit where the latency dynamics are different.

---

### 5.3 🟡 Talent and knowledge concentration risk

**Finding:** The system appears to be built and operated by a single developer. Every piece of institutional knowledge — model reasoning, operational procedures, API quirks — is in one person's head.

**Actions:**
- [ ] Document every non-obvious decision in the codebase and `docs/`. The current documentation is strong for a solo project but would not allow a new hire to operate the system independently.
- [ ] Hire a second quantitative engineer before live trading begins. At minimum, establish a "key person" contingency plan.
- [ ] Add a "system design" document that a new hire could read in one day and understand the entire architecture, edge thesis, and risk model without reading code.

---

### 5.4 🟡 No capital raising strategy

**Finding:** The default bankroll is $100k USDC. At 10% max single exposure and 25% Kelly cap, the maximum position size is roughly $2,500–$10,000. Even at a 50% annual return (extremely optimistic), this generates $50k/year — not a firm, just a personal trading account.

**Actions:**
- [ ] Define the minimum bankroll at which the strategy is economically meaningful (Kelly sizing becomes sub-optimal below ~$50k due to minimum contract sizes and fees).
- [ ] Model the capacity constraint: at what AUM does Kalshi's open interest limit the strategy's returns? At $1M+ deployed, market impact may reduce edge materially.
- [ ] If external capital is sought, consult a securities attorney on whether a fund structure (3(c)(1) exempt fund, family office, etc.) is appropriate.
- [ ] Alternatively, pursue a prop trading arrangement with a funded account from an established firm — provides capital without regulatory burden.

---

### 5.5 🟡 No competitive moat analysis

**Finding:** Latency arbitrage on prediction markets is a documented strategy. Kalshi has grown significantly since 2022, and it is reasonable to assume other quantitative firms are pursuing similar strategies. The system has not characterized who its competitors are or how durable the edge is as competition increases.

**Actions:**
- [ ] Measure the edge decay curve: plot `mean_edge` per fill as a function of calendar date. If edge is shrinking over time, competition is increasing.
- [ ] Monitor Kalshi's order book update frequency: if Kalshi starts updating prices in < 1 second after CEX moves, the latency arb window may close.
- [ ] Identify the system's structural advantages over likely competitors: superior vol model, faster infrastructure, better signal detection. Invest in the advantages that are hardest to replicate.
- [ ] Consider whether maker liquidity provision (posting limit orders) is a more sustainable competitive position than latency arb as the market matures.

---

### 5.6 🟢 Marketing site is ahead of the product

**Finding:** `index.html` presents Kinzie as an institutional-grade trading firm with a "Systems" section and detailed risk framework. The actual product is a paper-trading script with 8 fills. This disconnect creates reputational risk if the site is seen by prospective counterparties, regulators, or talent before live performance is established.

**Actions:**
- [ ] Add a clear disclosure to the public site that the system is in paper-trading / research phase and has no live track record.
- [ ] Gate detailed strategy descriptions behind a login or NDA until a live track record exists.
- [ ] Use the marketing investment to build a talent pipeline: post a quantitative developer role once live trading is validated.

---

## Summary — Priority Order

| Priority | Action |
|----------|--------|
| 1 | Implement `model_prob` logging into `_OpenRow` for calibration measurement |
| 2 | Enable WAL mode and automated DB backup to object storage |
| 3 | Implement alerting (Slack/PagerDuty) for circuit breakers, feed outages, stuck positions |
| 4 | Implement live order placement (`KalshiClient.place_order()`) and test in paper mode |
| 5 | Subscribe to CF Benchmarks index feed and use it as the pricing input |
| 6 | Implement limit order support to reduce effective taker cost |
| 7 | Add data freshness guard in `ScannerAgent` to reject stale CEX data |
| 8 | Incorporate the trading entity as an LLC and consult a commodities attorney |
| 9 | Set up tax accounting infrastructure before first live trade |
| 10 | Expand market universe to Kalshi macro contracts (Fed, CPI, NFP) |
| 11 | Deploy to co-located infrastructure and measure actual Kalshi round-trip latency |
| 12 | Build a vol term structure: separate vol windows per expiry horizon |
| 13 | Migrate from SQLite to PostgreSQL before live capital exceeds $100k |
| 14 | Add a `/health` HTTP endpoint for external uptime monitoring |
| 15 | Add slippage model to paper fills calibrated to Kalshi order book depth |
| 16 | Add regime detection and parameter adjustment for high/low vol environments |
| 17 | Document a key-person contingency plan and begin recruiting a second quantitative engineer |
| 18 | Establish a formal audited track record at ≥200 live fills |

---

*This audit was generated from a full read of all source files, configuration, agent implementations, documentation, and research tools in the repository as of the date above. It reflects the state of the system at commit time and should be revisited after each major milestone (live trading launch, 100 fills, $1M AUM).*
