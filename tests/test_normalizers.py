from pathlib import Path

import pytest

from vequil.normalizers import generate_unified_ledger, normalize_freedompay


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generate_unified_ledger_assigns_transaction_ids_and_schema() -> None:
    ledger = generate_unified_ledger(PROJECT_ROOT / "data" / "raw")

    assert ledger["transaction_id"].tolist()[:3] == ["txn-00001", "txn-00002", "txn-00003"]
    assert ledger["transaction_id"].is_unique
    assert len(ledger) == 25000


def test_freedompay_timestamps_are_converted_to_local_business_date() -> None:
    normalized = normalize_freedompay(PROJECT_ROOT / "data" / "raw" / "freedompay_settlement.csv")
    target_row = normalized.loc[normalized["reference_id"] == "REQ-FP-200000"].iloc[0]

    assert target_row["transaction_at"].isoformat(sep=" ") == "2026-04-03 19:42:57"
    assert target_row["business_date"] == "2026-04-03"


def test_normalizer_raises_clear_error_when_required_columns_are_missing(tmp_path: Path) -> None:
    path = tmp_path / "freedompay_settlement.csv"
    path.write_text("Timestamp,Store_ID\n2026-03-26T18:15:00Z,FP-CONC-MAIN\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        normalize_freedompay(path)
