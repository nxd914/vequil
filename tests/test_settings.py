from pathlib import Path

from vequil.settings import load_expected_sales_config, load_processor_configs


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_load_processor_configs_reads_json_mappings() -> None:
    configs = load_processor_configs(PROJECT_ROOT / "configs" / "processors.json")

    assert [config.name for config in configs] == ["Shift4", "FreedomPay", "Amazon JWO", "SeatGeek", "Tapin2"]
    assert configs[1].target_timezone == "America/Chicago"
    assert configs[0].column_map["reference_id"] == "InvoiceNumber"


def test_load_expected_sales_config_reads_thresholds() -> None:
    config = load_expected_sales_config(PROJECT_ROOT / "configs" / "expected_sales.json")

    assert config.filename == "pos_expected_sales.csv"
    assert config.amount_tolerance == 5.0
    assert config.count_tolerance == 0
