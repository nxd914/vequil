from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd


Normalizer = Callable[[Path], pd.DataFrame]


LEDGER_COLUMNS = [
    "transaction_id",
    "transaction_at",
    "business_date",
    "processor",
    "venue_area",
    "terminal_id",
    "reference_id",
    "auth_code",
    "tender_type",
    "transaction_type",
    "amount",
    "settlement_status",
    "batch_id",
    "source_file",
]

EXPECTED_SALES_COLUMNS = [
    "expected_group_id",
    "business_date",
    "source_system",
    "venue_area",
    "expected_amount",
    "expected_transaction_count",
    "source_file",
]

EXPECTED_COMPARISON_COLUMNS = [
    "expected_group_id",
    "business_date",
    "source_system",
    "venue_area",
    "expected_amount",
    "settled_amount",
    "variance_amount",
    "expected_transaction_count",
    "settled_transaction_count",
    "finding_count",
]

REVIEWED_LEDGER_COLUMNS = LEDGER_COLUMNS + [
    "discrepancy_count",
    "discrepancy_types",
    "recommended_actions",
]

DISCREPANCY_COLUMNS = [
    "record_type",
    "transaction_id",
    "transaction_at",
    "business_date",
    "processor",
    "source_system",
    "venue_area",
    "terminal_id",
    "reference_id",
    "transaction_type",
    "amount",
    "settlement_status",
    "auth_code",
    "expected_amount",
    "settled_amount",
    "variance_amount",
    "expected_transaction_count",
    "settled_transaction_count",
    "discrepancy_type",
    "diagnosis",
    "recommended_action",
]

RECENT_ACTIVITY_COLUMNS = [
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
    "discrepancy_count",
    "discrepancy_types",
    "recommended_actions",
]

SETTLED_STATUSES = {"SETTLED", "CAPTURED", "CLEARED"}


@dataclass(frozen=True)
class ProcessorSpec:
    name: str
    filename: str
    required_columns: tuple[str, ...]
    normalizer: Normalizer
