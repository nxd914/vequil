from pathlib import Path

from vequil.expected_sales import (
    build_expected_sales_comparison,
    build_expected_sales_discrepancies,
    load_expected_sales,
)
from vequil.normalizers import generate_unified_ledger
from vequil.settings import load_expected_sales_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_expected_sales_comparison_flags_variance_groups() -> None:
    raw_dir = PROJECT_ROOT / "data" / "raw"
    ledger = generate_unified_ledger(raw_dir)
    expected_config = load_expected_sales_config(PROJECT_ROOT / "configs" / "expected_sales.json")
    expected_sales = load_expected_sales(raw_dir, expected_config)

    comparison = build_expected_sales_comparison(ledger, expected_sales, expected_config)
    discrepancies = build_expected_sales_discrepancies(comparison, expected_config)

    assert len(expected_sales) == 13
    assert len(comparison.loc[comparison["finding_count"] > 0]) == 2
    assert len(discrepancies) == 2
