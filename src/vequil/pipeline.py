from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

import requests
from .config import OUTPUT_DIR, RAW_DATA_DIR, SLACK_WEBHOOK_URL
from .expected_sales import (
    build_expected_sales_comparison,
    build_expected_sales_discrepancies,
    load_expected_sales,
)
from .notifier import notifier
from .normalizers import generate_unified_ledger
from .rules import build_discrepancy_table, build_reviewed_ledger
from .schema import DISCREPANCY_COLUMNS, EXPECTED_COMPARISON_COLUMNS, RECENT_ACTIVITY_COLUMNS
from .settings import load_expected_sales_config


@dataclass(frozen=True)
class PipelineArtifacts:
    ledger_path: Path
    discrepancy_path: Path
    comparison_path: Path
    dashboard_path: Path
    report_path: Path


def build_dashboard_payload(
    reviewed: pd.DataFrame,
    discrepancies: pd.DataFrame,
    expected_comparison: pd.DataFrame,
) -> dict:
    flagged_transactions = reviewed["discrepancy_count"].gt(0)
    total_volume = float(reviewed["amount"].sum())
    cleared_volume = float(reviewed.loc[~flagged_transactions, "amount"].sum())
    at_risk_volume = float(reviewed.loc[flagged_transactions, "amount"].sum())
    expected_sales_volume = float(expected_comparison["expected_amount"].sum())
    expected_variance = float(expected_comparison["variance_amount"].sum())
    metrics = {
        "total_transactions": int(len(reviewed)),
        "flagged_transactions": int(flagged_transactions.sum()),
        "total_findings": int(len(discrepancies)),
        "total_volume": round(total_volume, 2),
        "cleared_volume": round(cleared_volume, 2),
        "at_risk_volume": round(at_risk_volume, 2),
        "expected_sales_volume": round(expected_sales_volume, 2),
        "net_expected_variance": round(expected_variance, 2),
    }

    processor_summary = (
        reviewed.groupby("processor", dropna=False)
        .agg(
            transactions=("reference_id", "count"),
            total_amount=("amount", "sum"),
            flagged_transactions=("discrepancy_count", lambda s: int((s > 0).sum())),
        )
        .reset_index()
    )
    findings_by_processor = (
        discrepancies.groupby("processor", dropna=False)
        .agg(findings=("transaction_id", "count"))
        .reset_index()
    )
    processor_summary = processor_summary.merge(
        findings_by_processor, on="processor", how="left"
    )
    processor_summary["findings"] = processor_summary["findings"].fillna(0).astype(int)

    discrepancy_summary = (
        discrepancies.groupby("discrepancy_type", dropna=False)
        .agg(
            count=("transaction_id", "count"),
            total_amount=("amount", "sum"),
        )
        .reset_index()
        .sort_values(["count", "total_amount"], ascending=[False, False])
    )

    expected_variance_summary = expected_comparison.loc[
        expected_comparison["finding_count"].gt(0),
        EXPECTED_COMPARISON_COLUMNS,
    ].copy()
    expected_variance_summary = expected_variance_summary.sort_values(
        ["finding_count", "variance_amount"],
        ascending=[False, False],
        key=lambda series: series.abs() if series.name == "variance_amount" else series,
    ).head(8)

    recent = reviewed.sort_values("transaction_at", ascending=False).head(12)
    discrepancy_rows = _serialize_records(
        discrepancies.sort_values(
            ["business_date", "record_type", "transaction_at", "reference_id"],
            ascending=[False, True, False, True],
            na_position="last",
        )[DISCREPANCY_COLUMNS]
    )
    recent = _serialize_records(recent[RECENT_ACTIVITY_COLUMNS])
    payload = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "metrics": metrics,
        "processor_summary": processor_summary.to_dict(orient="records"),
        "discrepancy_summary": discrepancy_summary.to_dict(orient="records"),
        "expected_variance_summary": _serialize_records(expected_variance_summary),
        "discrepancies": discrepancy_rows,
        "recent_activity": recent,
    }
    return payload


def _serialize_records(df: pd.DataFrame) -> list[dict]:
    serializable = df.copy()
    for column in serializable.columns:
        if pd.api.types.is_datetime64_any_dtype(serializable[column]):
            serializable[column] = serializable[column].dt.strftime("%Y-%m-%d %H:%M:%S")
    serializable = serializable.fillna("")
    return serializable.to_dict(orient="records")


def run_pipeline(
    raw_data_dir: Path = RAW_DATA_DIR, 
    output_dir: Path = OUTPUT_DIR,
    event_id: str | None = None
) -> PipelineArtifacts:
    # If an event_id is provided, we nest the output in a specific folder. 
    # Otherwise we use the base output_dir for the "current" view.
    if event_id:
        output_dir = output_dir / "events" / event_id

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = generate_unified_ledger(raw_data_dir=raw_data_dir)
    transaction_discrepancies = build_discrepancy_table(ledger)
    reviewed = build_reviewed_ledger(ledger, transaction_discrepancies)

    expected_sales_config = load_expected_sales_config()
    expected_sales = load_expected_sales(raw_data_dir=raw_data_dir, expected_config=expected_sales_config)
    expected_comparison = build_expected_sales_comparison(
        ledger, expected_sales, expected_sales_config
    )
    expected_discrepancies = build_expected_sales_discrepancies(
        expected_comparison, expected_sales_config
    )

    discrepancies = pd.concat(
        [transaction_discrepancies, expected_discrepancies], ignore_index=True
    )
    from .agent import diagnose_discrepancies
    discrepancies = diagnose_discrepancies(discrepancies)
    dashboard = build_dashboard_payload(reviewed, discrepancies, expected_comparison)

    report_path = output_dir / "reconciliation_report.xlsx"
    _write_excel_report(reviewed, discrepancies, expected_comparison, report_path)

    # ── Financial Alerts ──────────────────────────────────────
    net_variance = dashboard["metrics"]["net_expected_variance"]
    notifier.notify_variance_alert(
        event_id=event_id, 
        amount=net_variance, 
        count=len(discrepancies)
    )

    ledger_path = output_dir / "unified_ledger.csv"
    discrepancy_path = output_dir / "discrepancies.csv"
    comparison_path = output_dir / "expected_sales_comparison.csv"
    dashboard_path = output_dir / "dashboard.json"

    reviewed.to_csv(ledger_path, index=False)
    discrepancies.to_csv(discrepancy_path, index=False)
    expected_comparison.to_csv(comparison_path, index=False)
    dashboard_path.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")

    return PipelineArtifacts(
        ledger_path=ledger_path,
        discrepancy_path=discrepancy_path,
        comparison_path=comparison_path,
        dashboard_path=dashboard_path,
        report_path=report_path,
    )


def _write_excel_report(
    reviewed: pd.DataFrame,
    discrepancies: pd.DataFrame,
    expected_comparison: pd.DataFrame,
    path: Path,
) -> None:
    """Write a formatted Excel report with the reconciliation findings."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # 1. Summary Sheet
        summary_data = {
            "Metric": [
                "Total Transactions",
                "Flagged Transactions",
                "Total Finding Count",
                "Total Settled Volume",
                "At-Risk Volume",
                "Net Expected Variance",
            ],
            "Value": [
                len(reviewed),
                int(reviewed["discrepancy_count"].gt(0).sum()),
                len(discrepancies),
                reviewed["amount"].sum(),
                reviewed.loc[reviewed["discrepancy_count"].gt(0), "amount"].sum(),
                expected_comparison["variance_amount"].sum(),
            ],
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

        # 2. Exceptions Sheet
        exceptions = discrepancies.sort_values(
            ["business_date", "transaction_at"], ascending=False
        )
        exceptions.to_excel(writer, sheet_name="Exceptions", index=False)

        # 3. Full Ledger
        reviewed.to_excel(writer, sheet_name="Unified Ledger", index=False)

        # Formatting
        workbook = writer.book
        for sheetname in workbook.sheetnames:
            worksheet = workbook[sheetname]
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                worksheet.column_dimensions[column].width = min(max_length + 2, 60)




if __name__ == "__main__":
    artifacts = run_pipeline()
    print(f"Wrote {artifacts.ledger_path}")
    print(f"Wrote {artifacts.discrepancy_path}")
    print(f"Wrote {artifacts.comparison_path}")
    print(f"Wrote {artifacts.dashboard_path}")
