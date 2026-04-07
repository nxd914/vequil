from __future__ import annotations

import pandas as pd

from .schema import DISCREPANCY_COLUMNS, REVIEWED_LEDGER_COLUMNS, SETTLED_STATUSES


RULE_DEFINITIONS = (
    (
        "Unsettled status",
        "Confirm if this is a timing delay or a true settlement failure.",
        lambda ledger: ~ledger["settlement_status"].isin(SETTLED_STATUSES),
    ),
    (
        "Missing auth code",
        "Review processor detail and verify authorization before close.",
        lambda ledger: ledger["processor"].isin(["Shift4", "FreedomPay"])
        & ledger["auth_code"].astype(str).str.strip().eq(""),
    ),
    (
        "Refund requires offset review",
        "Match this refund against the original sale and settlement batch.",
        lambda ledger: ledger["transaction_type"].eq("REFUND"),
    ),
    (
        "Duplicate reference",
        "Check for duplicate export rows or double settlement.",
        lambda ledger: ledger.duplicated(subset=["processor", "reference_id"], keep=False),
    ),
    (
        "High-value review",
        "Large transaction. Validate amount and batch before close.",
        lambda ledger: ledger["amount"].abs().ge(1000),
    ),
)


def build_discrepancy_table(ledger: pd.DataFrame) -> pd.DataFrame:
    findings: list[pd.DataFrame] = []
    for rule_order, (discrepancy_type, recommended_action, mask_builder) in enumerate(
        RULE_DEFINITIONS
    ):
        mask = mask_builder(ledger)
        if not mask.any():
            continue
        finding_rows = ledger.loc[
            mask,
            [
                "transaction_id",
                "transaction_at",
                "business_date",
                "processor",
                "venue_area",
                "terminal_id",
                "reference_id",
                "transaction_type",
                "amount",
                "settlement_status",
                "auth_code",
            ],
        ].copy()
        finding_rows["record_type"] = "transaction"
        finding_rows["rule_order"] = rule_order
        finding_rows["source_system"] = ""
        finding_rows["expected_amount"] = pd.NA
        finding_rows["settled_amount"] = pd.NA
        finding_rows["variance_amount"] = pd.NA
        finding_rows["expected_transaction_count"] = pd.NA
        finding_rows["settled_transaction_count"] = pd.NA
        finding_rows["discrepancy_type"] = discrepancy_type
        finding_rows["diagnosis"] = ""
        finding_rows["recommended_action"] = recommended_action
        findings.append(finding_rows)

    if not findings:
        return pd.DataFrame(columns=DISCREPANCY_COLUMNS)

    discrepancies = pd.concat(findings, ignore_index=True)
    discrepancies = discrepancies.sort_values(
        ["transaction_at", "processor", "reference_id", "rule_order"],
        kind="mergesort",
    ).reset_index(drop=True)
    discrepancies = discrepancies.drop(columns=["rule_order"])
    return discrepancies.loc[:, DISCREPANCY_COLUMNS]


def build_reviewed_ledger(ledger: pd.DataFrame, discrepancies: pd.DataFrame) -> pd.DataFrame:
    reviewed = ledger.copy()
    if discrepancies.empty:
        reviewed["discrepancy_count"] = 0
        reviewed["discrepancy_types"] = ""
        reviewed["recommended_actions"] = ""
        return reviewed.loc[:, REVIEWED_LEDGER_COLUMNS]

    aggregated = (
        discrepancies.groupby("transaction_id", sort=False)
        .agg(
            discrepancy_count=("discrepancy_type", "count"),
            discrepancy_types=("discrepancy_type", _join_distinct),
            recommended_actions=("recommended_action", _join_distinct),
        )
        .reset_index()
    )
    reviewed = reviewed.merge(aggregated, on="transaction_id", how="left")
    reviewed["discrepancy_count"] = reviewed["discrepancy_count"].fillna(0).astype(int)
    reviewed["discrepancy_types"] = reviewed["discrepancy_types"].fillna("")
    reviewed["recommended_actions"] = reviewed["recommended_actions"].fillna("")
    return reviewed.loc[:, REVIEWED_LEDGER_COLUMNS]


def _join_distinct(values: pd.Series) -> str:
    ordered_unique = list(dict.fromkeys(values.tolist()))
    return " | ".join(ordered_unique)
