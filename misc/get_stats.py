import json
from pathlib import Path
import pandas as pd
from vequil.expected_sales import build_expected_sales_comparison, build_expected_sales_discrepancies, load_expected_sales
from vequil.normalizers import generate_unified_ledger, normalize_freedompay
from vequil.settings import load_expected_sales_config
from vequil.pipeline import run_pipeline

PROJECT_ROOT = Path('.')
artifacts = run_pipeline(PROJECT_ROOT / "data" / "raw", PROJECT_ROOT / "tmp")
reviewed = pd.read_csv(artifacts.ledger_path)
discrepancies = pd.read_csv(artifacts.discrepancy_path)
comparison = pd.read_csv(artifacts.comparison_path)
dashboard = json.loads(artifacts.dashboard_path.read_text(encoding="utf-8"))

print(f"discrepancies len: {len(discrepancies)}")
print(f"comparison len: {len(comparison)}")
print(f"dashboard metrics: {dashboard['metrics']}")

duplicate_rows = discrepancies.loc[discrepancies["discrepancy_type"] == "Duplicate reference"]
print(f"duplicate_rows: {duplicate_rows['transaction_id'].nunique()}")

expected_rows = discrepancies.loc[discrepancies["record_type"] == "expected_sales"]
print(f"expected sales discrepancy types: {set(expected_rows['discrepancy_type'])}")

flagged_groups = comparison.loc[comparison["finding_count"] > 0, "expected_group_id"]
print(f"flagged_groups: {set(flagged_groups)}")

raw_dir = PROJECT_ROOT / "data" / "raw"
ledger = generate_unified_ledger(raw_dir)
expected_config = load_expected_sales_config(PROJECT_ROOT / "configs" / "expected_sales.json")
expected_sales = load_expected_sales(raw_dir, expected_config)
c2 = build_expected_sales_comparison(ledger, expected_sales, expected_config)
d2 = build_expected_sales_discrepancies(c2, expected_config)
print(f"expected sales comparison flagged: {len(c2.loc[c2['finding_count'] > 0])}")
print(f"expected sales discrepancies: {len(d2)}")

