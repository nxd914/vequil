from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import RAW_DATA_DIR
from .schema import LEDGER_COLUMNS
from .settings import ProcessorConfig, get_processor_config, load_processor_configs


NORMALIZED_FIELDS = (
    "venue_area",
    "terminal_id",
    "reference_id",
    "auth_code",
    "tender_type",
    "transaction_type",
    "amount",
    "settlement_status",
    "batch_id",
)


def _read_csv(path: Path, processor_config: ProcessorConfig) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing_columns = [column for column in processor_config.required_columns if column not in df.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(
            f"{processor_config.name} file {path.name} is missing required columns: {missing}"
        )
    return df


def _build_timestamp(df: pd.DataFrame, processor_config: ProcessorConfig) -> pd.Series:
    if len(processor_config.timestamp_columns) == 1:
        raw_timestamp = df[processor_config.timestamp_columns[0]].astype(str)
    else:
        raw_timestamp = (
            df[list(processor_config.timestamp_columns)].astype(str).agg(" ".join, axis=1)
        )

    timestamps = pd.to_datetime(
        raw_timestamp,
        format=processor_config.date_format,
        utc=processor_config.source_timezone is not None,
    )
    timezone = getattr(timestamps.dt, "tz", None)

    if processor_config.source_timezone and timezone is None:
        timestamps = timestamps.dt.tz_localize(processor_config.source_timezone)
    if processor_config.target_timezone:
        timestamps = timestamps.dt.tz_convert(processor_config.target_timezone)
    if getattr(timestamps.dt, "tz", None) is not None:
        timestamps = timestamps.dt.tz_localize(None)
    return timestamps


def normalize_processor(path: Path, processor_config: ProcessorConfig) -> pd.DataFrame:
    df = _read_csv(path, processor_config)
    transaction_at = _build_timestamp(df, processor_config)
    normalized: dict[str, object] = {
        "transaction_at": transaction_at,
        "business_date": transaction_at.dt.strftime("%Y-%m-%d"),
        "processor": processor_config.name,
        "source_file": path.name,
    }

    for field in NORMALIZED_FIELDS:
        if field in processor_config.column_map:
            value = df[processor_config.column_map[field]]
        else:
            value = pd.Series(
                [processor_config.constants.get(field, "")] * len(df),
                index=df.index,
            )

        if field == "amount":
            if processor_config.amount_format == "currency" or (
                isinstance(value.iloc[0], str) and ("$" in value.iloc[0] or "," in value.iloc[0])
            ):
                # Handle cases like "$1,234.56"
                value = value.astype(str).str.replace(r"[$,]", "", regex=True)
            normalized[field] = pd.Series(value, index=df.index).astype(float)
        elif field == "auth_code":
            normalized[field] = pd.Series(value, index=df.index).fillna("").astype(str)
        else:
            normalized[field] = value

    return pd.DataFrame(normalized).loc[:, LEDGER_COLUMNS[1:]]


def normalize_shift4(path: Path) -> pd.DataFrame:
    return normalize_processor(path, get_processor_config("Shift4"))


def normalize_freedompay(path: Path) -> pd.DataFrame:
    return normalize_processor(path, get_processor_config("FreedomPay"))


def normalize_amazon(path: Path) -> pd.DataFrame:
    return normalize_processor(path, get_processor_config("Amazon JWO"))


def generate_unified_ledger(
    raw_data_dir: Path = RAW_DATA_DIR,
    processor_configs: tuple[ProcessorConfig, ...] | None = None,
) -> pd.DataFrame:
    configs = processor_configs or load_processor_configs()
    frames = [
        normalize_processor(raw_data_dir / processor_config.filename, processor_config)
        for processor_config in configs
    ]
    ledger = pd.concat(frames, ignore_index=True)
    ledger["amount"] = ledger["amount"].astype(float).round(2)
    ledger = ledger.sort_values(["transaction_at", "processor", "reference_id"]).reset_index(drop=True)
    ledger.insert(0, "transaction_id", [f"txn-{index:05d}" for index in range(1, len(ledger) + 1)])
    return ledger.loc[:, LEDGER_COLUMNS]
