import json
from pathlib import Path

import pandas as pd

from vequil.pipeline import run_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_writes_reviewed_ledger_and_finding_table(tmp_path: Path) -> None:
    artifacts = run_pipeline(
        raw_data_dir=PROJECT_ROOT / "data" / "raw",
        output_dir=tmp_path,
    )

    reviewed = pd.read_csv(artifacts.ledger_path)
    discrepancies = pd.read_csv(artifacts.discrepancy_path)
    comparison = pd.read_csv(artifacts.comparison_path)
    dashboard = json.loads(artifacts.dashboard_path.read_text(encoding="utf-8"))

    assert len(reviewed) == 25000
    assert len(discrepancies) == 272
    assert len(comparison) == 13
    assert reviewed["discrepancy_count"].sum() == 270
    assert int((reviewed["discrepancy_count"] > 0).sum()) == dashboard["metrics"]["flagged_transactions"]
    assert dashboard["metrics"]["total_findings"] == len(discrepancies)
    assert dashboard["metrics"]["at_risk_volume"] == 71274.04
    assert dashboard["metrics"]["expected_sales_volume"] == 2534797.63
    assert dashboard["metrics"]["net_expected_variance"] == -10253.23


def test_pipeline_preserves_duplicate_rows_in_discrepancy_table(tmp_path: Path) -> None:
    artifacts = run_pipeline(
        raw_data_dir=PROJECT_ROOT / "data" / "raw",
        output_dir=tmp_path,
    )
    discrepancies = pd.read_csv(artifacts.discrepancy_path)

    duplicate_rows = discrepancies.loc[
        discrepancies["discrepancy_type"] == "Duplicate reference"
    ]
    assert duplicate_rows["transaction_id"].nunique() == 10


def test_pipeline_includes_expected_sales_findings(tmp_path: Path) -> None:
    artifacts = run_pipeline(
        raw_data_dir=PROJECT_ROOT / "data" / "raw",
        output_dir=tmp_path,
    )
    discrepancies = pd.read_csv(artifacts.discrepancy_path)
    comparison = pd.read_csv(artifacts.comparison_path)

    expected_rows = discrepancies.loc[discrepancies["record_type"] == "expected_sales"]
    assert set(expected_rows["discrepancy_type"]) == {
        "Expected sales exceed settlement",
    }
    flagged_groups = comparison.loc[comparison["finding_count"] > 0, "expected_group_id"]
    assert set(flagged_groups) == {
        "2026-04-03:MERCH-MAIN",
        "2026-04-03:JWO-STORE-1",
    }
