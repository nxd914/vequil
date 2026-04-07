from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import RAW_DATA_DIR
from .schema import DISCREPANCY_COLUMNS, EXPECTED_COMPARISON_COLUMNS, EXPECTED_SALES_COLUMNS
from .settings import ExpectedSalesConfig, load_expected_sales_config


def load_expected_sales(
    raw_data_dir: Path = RAW_DATA_DIR,
    expected_config: ExpectedSalesConfig | None = None,
) -> pd.DataFrame:
    config = expected_config or load_expected_sales_config()
    path = raw_data_dir / config.filename
    df = pd.read_csv(path)

    missing_columns = [column for column in config.required_columns if column not in df.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"{config.name} file {path.name} is missing required columns: {missing}")

    normalized = pd.DataFrame(
        {
            "business_date": pd.to_datetime(df[config.field_map["business_date"]]).dt.strftime("%Y-%m-%d"),
            "source_system": df[config.field_map["source_system"]],
            "venue_area": df[config.field_map["venue_area"]],
            "terminal_id": df[config.field_map.get("terminal_id", "")].fillna("") if "terminal_id" in config.field_map else "",
            "expected_amount": df[config.field_map["expected_amount"]].astype(float).round(2),
            "expected_transaction_count": df[config.field_map["expected_transaction_count"]].astype(int),
            "source_file": path.name,
        }
    )
    normalized.insert(
        0,
        "expected_group_id",
        normalized["business_date"] + ":" + normalized["venue_area"] + ":" + normalized["terminal_id"].astype(str),
    )
    return normalized.loc[:, EXPECTED_SALES_COLUMNS]


def build_expected_sales_comparison(
    ledger: pd.DataFrame,
    expected_sales: pd.DataFrame,
    expected_config: ExpectedSalesConfig,
) -> pd.DataFrame:
    group_cols = ["business_date", "venue_area"]
    if "terminal_id" in expected_config.field_map:
        group_cols.append("terminal_id")

    settlement_summary = (
        ledger.groupby(group_cols, dropna=False)
        .agg(
            settled_amount=("amount", "sum"),
            settled_transaction_count=("transaction_id", "count"),
        )
        .reset_index()
    )

    comparison = expected_sales.merge(
        settlement_summary,
        on=group_cols,
        how="outer",
    )
    comparison["source_system"] = comparison["source_system"].fillna(expected_config.name)
    comparison["expected_amount"] = comparison["expected_amount"].fillna(0.0).astype(float).round(2)
    comparison["settled_amount"] = comparison["settled_amount"].fillna(0.0).astype(float).round(2)
    comparison["expected_transaction_count"] = (
        comparison["expected_transaction_count"].fillna(0).astype(int)
    )
    comparison["settled_transaction_count"] = (
        comparison["settled_transaction_count"].fillna(0).astype(int)
    )
    comparison["expected_group_id"] = (
        comparison["business_date"].astype(str) + ":" + comparison["venue_area"].astype(str)
    )
    comparison["variance_amount"] = (
        comparison["settled_amount"] - comparison["expected_amount"]
    ).round(2)
    comparison["finding_count"] = comparison.apply(
        lambda row: len(_build_findings(row, expected_config)),
        axis=1,
    )
    comparison = comparison.sort_values(
        ["business_date", "venue_area"], ascending=[False, True]
    ).reset_index(drop=True)
    return comparison.loc[:, EXPECTED_COMPARISON_COLUMNS]


def build_expected_sales_discrepancies(
    comparison: pd.DataFrame,
    expected_config: ExpectedSalesConfig,
) -> pd.DataFrame:
    findings: list[dict[str, object]] = []
    for row in comparison.to_dict(orient="records"):
        for discrepancy_type, recommended_action in _build_findings(pd.Series(row), expected_config):
            findings.append(
                {
                    "record_type": "expected_sales",
                    "transaction_id": "",
                    "transaction_at": pd.NaT,
                    "business_date": row["business_date"],
                    "processor": "Expected Sales",
                    "source_system": row["source_system"],
                    "venue_area": row["venue_area"],
                    "terminal_id": "",
                    "reference_id": row["expected_group_id"],
                    "transaction_type": "SUMMARY",
                    "amount": row["variance_amount"],
                    "settlement_status": "",
                    "auth_code": "",
                    "expected_amount": row["expected_amount"],
                    "settled_amount": row["settled_amount"],
                    "variance_amount": row["variance_amount"],
                    "expected_transaction_count": row["expected_transaction_count"],
                    "settled_transaction_count": row["settled_transaction_count"],
                    "discrepancy_type": discrepancy_type,
                    "diagnosis": "",
                    "recommended_action": recommended_action,
                }
            )

    if not findings:
        return pd.DataFrame(columns=DISCREPANCY_COLUMNS)

    discrepancies = pd.DataFrame(findings)
    discrepancies = discrepancies.sort_values(
        ["business_date", "venue_area", "discrepancy_type"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
    return discrepancies.loc[:, DISCREPANCY_COLUMNS]


def _build_findings(
    row: pd.Series,
    expected_config: ExpectedSalesConfig,
) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    has_expected = row["expected_transaction_count"] > 0 or row["expected_amount"] != 0
    has_settlement = row["settled_transaction_count"] > 0 or row["settled_amount"] != 0
    variance = float(row["variance_amount"])
    count_delta = int(row["settled_transaction_count"] - row["expected_transaction_count"])

    if has_settlement and not has_expected:
        findings.append(
            (
                "Missing expected sales record",
                "Add or regenerate the POS summary feed for this business date and venue area.",
            )
        )
    if has_expected and not has_settlement:
        findings.append(
            (
                "Missing settlement activity",
                "Confirm settlement timing and verify whether processor data is missing for this area.",
            )
        )
    if has_expected and has_settlement and abs(variance) > expected_config.amount_tolerance:
        if variance > 0:
            discrepancy_type = "Settlement exceeds expected sales"
        else:
            discrepancy_type = "Expected sales exceed settlement"
        findings.append(
            (
                discrepancy_type,
                f"Investigate the variance against {row['source_system']} and explain the delta before close.",
            )
        )
    if has_expected and has_settlement and abs(count_delta) > expected_config.count_tolerance:
        findings.append(
            (
                "Settlement count mismatch",
                f"Review transaction counts against {row['source_system']} for duplicate rows or missing tickets.",
            )
        )
    return findings
