import pandas as pd
from vequil.agent import diagnose_discrepancies, create_prompt

def test_diagnose_discrepancies_appends_columns():
    df = pd.DataFrame([
        {
            "transaction_id": "txn-001",
            "processor": "Shift4",
            "reference_id": "123",
            "amount": 100.0,
            "discrepancy_type": "Unsettled status"
        }
    ])
    result = diagnose_discrepancies(df)
    
    assert "diagnosis" in result.columns
    assert "recommended_action" in result.columns
    assert len(result) == 1
    assert "offline" in result.iloc[0]["diagnosis"].lower()

def test_diagnose_handles_empty_dataframe():
    df = pd.DataFrame()
    result = diagnose_discrepancies(df)
    assert "diagnosis" in result.columns
    assert "recommended_action" in result.columns
    assert len(result) == 0

def test_create_prompt_handles_missing_data():
    row = pd.Series({"amount": pd.NA})
    prompt = create_prompt(row)
    assert "Amount:            Unknown" in prompt
    assert "Unknown Anomaly" in prompt
