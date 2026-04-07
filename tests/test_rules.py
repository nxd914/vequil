import pandas as pd

from vequil.rules import build_discrepancy_table, build_reviewed_ledger


def test_rules_emit_multiple_findings_for_one_transaction() -> None:
    ledger = pd.DataFrame(
        [
            {
                "transaction_id": "txn-00001",
                "transaction_at": pd.Timestamp("2026-03-26 20:00:00"),
                "business_date": "2026-03-26",
                "processor": "Shift4",
                "venue_area": "Suite Level",
                "terminal_id": "S4-01",
                "reference_id": "INV-100",
                "auth_code": "",
                "tender_type": "VI",
                "transaction_type": "SALE",
                "amount": 1500.0,
                "settlement_status": "PENDING",
                "batch_id": "B-1",
                "source_file": "shift4.csv",
            }
        ]
    )

    discrepancies = build_discrepancy_table(ledger)
    reviewed = build_reviewed_ledger(ledger, discrepancies)

    assert discrepancies["discrepancy_type"].tolist() == [
        "Unsettled status",
        "Missing auth code",
        "High-value review",
    ]
    assert reviewed.loc[0, "discrepancy_count"] == 3
    assert reviewed.loc[0, "discrepancy_types"] == (
        "Unsettled status | Missing auth code | High-value review"
    )


def test_duplicate_reference_finds_both_rows() -> None:
    ledger = pd.DataFrame(
        [
            {
                "transaction_id": "txn-00001",
                "transaction_at": pd.Timestamp("2026-03-26 20:00:00"),
                "business_date": "2026-03-26",
                "processor": "Shift4",
                "venue_area": "Suite Level",
                "terminal_id": "S4-01",
                "reference_id": "INV-100",
                "auth_code": "A1",
                "tender_type": "VI",
                "transaction_type": "SALE",
                "amount": 100.0,
                "settlement_status": "SETTLED",
                "batch_id": "B-1",
                "source_file": "shift4.csv",
            },
            {
                "transaction_id": "txn-00002",
                "transaction_at": pd.Timestamp("2026-03-26 20:01:00"),
                "business_date": "2026-03-26",
                "processor": "Shift4",
                "venue_area": "Suite Level",
                "terminal_id": "S4-01",
                "reference_id": "INV-100",
                "auth_code": "A1",
                "tender_type": "VI",
                "transaction_type": "SALE",
                "amount": 100.0,
                "settlement_status": "SETTLED",
                "batch_id": "B-1",
                "source_file": "shift4.csv",
            },
        ]
    )

    discrepancies = build_discrepancy_table(ledger)

    assert discrepancies["discrepancy_type"].tolist() == [
        "Duplicate reference",
        "Duplicate reference",
    ]
