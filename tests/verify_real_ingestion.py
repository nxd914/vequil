
import json
import pandas as pd
from pathlib import Path
from vequil.settings import ProcessorConfig
from vequil.normalizers import normalize_processor

def test_real_world_ingestion():
    tmp_dir = Path("tmp/test_ingestion")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Mock Shift4 with "Real" headers and currency symbols
    s4_path = tmp_dir / "real_shift4.csv"
    s4_data = pd.DataFrame({
        "Trans_Date": ["04/03/2026", "04/03/2026"],
        "Trans_Time": ["17:05:00", "17:10:00"],
        "Area": ["SEC-114", "SEC-302"],
        "Term": ["T101", "T102"],
        "Inv": ["S4-999", "S4-1000"],
        "Auth": ["A123", "A456"],
        "Card": ["VISA", "MC"],
        "Amt": ["$12.50", "$1,234.56"], # Real-world formatting
        "Stat": ["SETTLED", "SETTLED"],
        "BID": ["B1", "B1"]
    })
    s4_data.to_csv(s4_path, index=False)
    
    s4_config = ProcessorConfig(
        name="Shift4Real",
        filename="real_shift4.csv",
        timestamp_columns=("Trans_Date", "Trans_Time"),
        source_timezone=None,
        target_timezone=None,
        column_map={
            "venue_area": "Area",
            "terminal_id": "Term",
            "reference_id": "Inv",
            "auth_code": "Auth",
            "tender_type": "Card",
            "amount": "Amt",
            "settlement_status": "Stat",
            "batch_id": "BID"
        },
        constants={"transaction_type": "SALE"},
        date_format="%m/%d/%Y %H:%M:%S",
        amount_format="currency"
    )
    
    # Run Normalization
    df = normalize_processor(s4_path, s4_config)
    
    print("\n--- Normalized Data ---")
    print(df)
    
    # Assertions
    assert df.iloc[0]["amount"] == 12.50
    assert df.iloc[1]["amount"] == 1234.56
    assert str(df.iloc[0]["transaction_at"]) == "2026-04-03 17:05:00"
    
    print("\n✅ Verification Successful: Real-world date and currency formats parsed correctly.")

if __name__ == "__main__":
    try:
        test_real_world_ingestion()
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
