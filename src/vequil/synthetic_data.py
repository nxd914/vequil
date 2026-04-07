"""
synthetic_data.py — Agentic Ledger Version
Generates realistic, massive-scale AI agent action logs across four 
platform integrations: OpenClaw, Claude, LangChain, and OpenAI.

Intentionally injects anomalies for the Vequil audit engine:
  - OpenClaw:  50 FAILED_SYSCALL terminal drops
  - Claude:    30 missing auth/API keys
  - LangChain: 10 runaway loops (duplicate step IDs)
  - OpenAI:    10 high-cost reasoning calls (>$2.00)

Usage:
    python src/vequil/synthetic_data.py                   # default 25,000 actions
    python src/vequil/synthetic_data.py --count 100000    # stress test
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_COUNT = 25_000
DEFAULT_OUT   = Path("data/raw")
START_TIME    = datetime.strptime("2026-04-07 09:00:00", "%Y-%m-%d %H:%M:%S")
RNG           = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _action_timestamps(n: int) -> list[datetime]:
    """Uniform distribution over a 12-hour window."""
    minutes = RNG.uniform(0, 720, n)
    return [START_TIME + timedelta(minutes=float(m)) for m in minutes]


def _utc_str(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# OpenClaw (Browsing, Syscalls, File Edits)
# ---------------------------------------------------------------------------

def generate_openclaw(count: int, timestamps: list[datetime], out: Path) -> pd.DataFrame:
    projects = ["vequil-alpha", "shop-bot", "infra-agent"]
    costs    = RNG.uniform(0.01, 0.15, count).round(4)
    statuses = ["COMPLETED"] * count
    for i in range(50):                    # ← inject 50 failed syscalls
        statuses[i] = "FAILED_SYSCALL"

    df = pd.DataFrame({
        "Timestamp":    [_utc_str(t) for t in timestamps],
        "Project":      RNG.choice(projects, count),
        "SessionID":    [f"OC-SESS-{RNG.integers(1000, 9999)}" for _ in range(count)],
        "ActionID":     [f"ACT-OC-{100_000 + i}"              for i in range(count)],
        "ToolUsed":     RNG.choice(["shell", "browse", "edit", "read"], count),
        "Model":        ["gpt-4o"] * count,
        "ComputeCost":  costs,
        "TaskStatus":   statuses,
        "Deployment":   ["PROD-A"] * count,
    })
    df.to_csv(out / "openclaw_logs.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# Claude (Conversations & Reasoning)
# ---------------------------------------------------------------------------

def generate_claude(count: int, timestamps: list[datetime], out: Path) -> pd.DataFrame:
    apps    = ["CustomerSupport", "DocAnalyzer"]
    costs   = RNG.uniform(0.05, 0.40, count).round(4)
    auths   = [f"SK-ANT-{RNG.integers(1000, 9999)}" for _ in range(count)]
    for i in range(30):                    # ← inject 30 missing auth keys
        auths[i] = ""

    df = pd.DataFrame({
        "Created_At":        [_utc_str(t)             for t in timestamps],
        "App_Name":          RNG.choice(apps, count),
        "Conversation_Root": [f"CONV-{RNG.integers(10, 999)}" for _ in range(count)],
        "Message_UUID":      [f"MSG-{200_000 + i}"           for i in range(count)],
        "Auth_Key_ID":       auths,
        "Turn_Type":         ["AGENT_RESPONSE"] * count,
        "Token_Price":       costs,
        "State":             ["DONE"] * count,
        "Org_ID":            ["ORG-VEQUIL"] * count,
    })
    df.to_csv(out / "claude_audit.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# LangChain (Internal Chain Traces)
# ---------------------------------------------------------------------------

def generate_langchain(count: int, timestamps: list[datetime], out: Path) -> pd.DataFrame:
    costs     = RNG.uniform(0.001, 0.02, count).round(4)
    step_ids  = [f"STEP-{300_000 + i}" for i in range(count)]
    
    # ← inject 10 runaway loops (duplicate step IDs)
    for i in range(10):
        step_ids[count - 1 - i] = step_ids[i]

    df = pd.DataFrame({
        "StartTime":         [_utc_str(t) for t in timestamps],
        "TracePath":         ["ResearchAgent-Chain"] * count,
        "RunID":             [f"RUN-{400_000 + i}" for i in range(count)],
        "StepID":            step_ids,
        "EstimatedCost":     costs,
        "CompletionStatus":  ["SUCCESS"] * count,
        "ProjectID":         ["LC-DEFAULT"] * count,
    })
    df.to_csv(out / "langchain_trace.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# OpenAI (Direct API Usage)
# ---------------------------------------------------------------------------

def generate_openai(count: int, timestamps: list[datetime], out: Path) -> pd.DataFrame:
    costs = RNG.uniform(0.01, 0.50, count).round(4)
    
    # ← inject 10 high-cost reasoning calls (triggers audit rule)
    for i in range(10):
        costs[i] = round(float(RNG.uniform(2.50, 15.00)), 4)

    df = pd.DataFrame({
        "RequestTime":       [_utc_str(t) for t in timestamps],
        "AppID":             ["Main-App-GPT4"] * count,
        "UserSID":           [f"USR-{RNG.integers(1, 999)}" for _ in range(count)],
        "ReqID":             [f"OAI-{500_000 + i}" for i in range(count)],
        "ApiKeyLast4":       [f"{RNG.integers(1000, 9999)}" for _ in range(count)],
        "ModelName":         RNG.choice(["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], count),
        "CallType":          ["chat.completion"] * count,
        "PriceUSD":          costs,
        "ResponseCode":      ["200"] * count,
        "BillingCycle":      ["APR-2026"] * count,
    })
    df.to_csv(out / "openai_usage.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# Baseline Resource Allocation
# ---------------------------------------------------------------------------

def generate_resource_baseline(
    oc_df: pd.DataFrame,
    cl_df: pd.DataFrame,
    lc_df: pd.DataFrame,
    oa_df: pd.DataFrame,
    out: Path,
) -> None:
    rows: list[dict] = []

    def _area_rows(df, cost_col, name, proj_col="Project"):
        for proj in df[proj_col].unique():
            sub        = df[df[proj_col] == proj]
            actual_vol = float(sub[cost_col].sum())
            actual_count = len(sub)
            rows.append({
                "BusinessDate":              "2026-04-07",
                "SourceSystem":              name,
                "VenueArea":                 proj,
                "ExpectedAmount":            round(actual_vol * 1.05, 4), # 5% buffer
                "ExpectedTransactionCount":  actual_count,
            })

    _area_rows(oc_df, "ComputeCost", "OpenClaw", "Project")
    _area_rows(cl_df, "Token_Price", "Claude",   "App_Name")
    _area_rows(lc_df, "EstimatedCost", "LangChain", "TracePath")
    _area_rows(oa_df, "PriceUSD",      "OpenAI",    "AppID")

    pd.DataFrame(rows).to_csv(out / "pos_expected_sales.csv", index=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate(num_actions: int = DEFAULT_COUNT, output_dir: Path = DEFAULT_OUT) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Distribute volume: OpenClaw 40%, Claude 30%, LangChain 15%, OpenAI 15%
    oc_n  = int(num_actions * 0.40)
    cl_n  = int(num_actions * 0.30)
    lc_n  = int(num_actions * 0.15)
    oa_n  = num_actions - oc_n - cl_n - lc_n

    all_ts = _action_timestamps(num_actions)

    oc_df = generate_openclaw(oc_n, all_ts[:oc_n], output_dir)
    cl_df = generate_claude(cl_n,   all_ts[oc_n:oc_n+cl_n], output_dir)
    lc_df = generate_langchain(lc_n, all_ts[oc_n+cl_n:oc_n+cl_n+lc_n], output_dir)
    oa_df = generate_openai(oa_n,    all_ts[oc_n+cl_n+lc_n:], output_dir)

    generate_resource_baseline(oc_df, cl_df, lc_df, oa_df, output_dir)

    print(f"\n✅ Generated {num_actions:,} agent actions across 4 platforms:")
    print(f"   OpenClaw:  {oc_n:>6,}  (includes 50 FAILED_SYSCALL anomalies)")
    print(f"   Claude:    {cl_n:>6,}  (includes 30 missing auth keys)")
    print(f"   LangChain: {lc_n:>6,}  (includes 10 runaway loops)")
    print(f"   OpenAI:    {oa_n:>6,}  (includes 10 high-cost audits)")
    print(f"\n   Output → {output_dir}/\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vequil synthetic agent data generator")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help="Total actions to generate (default: 25,000)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Output directory (default: data/raw)")
    args = parser.parse_args()
    generate(args.count, args.out)
