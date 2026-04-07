# Vequil Agent
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![Status: Prototype](https://img.shields.io/badge/Status-Prototype-blue.svg)]()

---

**Modular, engine-first framework for reconciling fragmented payment processor exports in sports and live venue operations. Designed for deterministic settlement validation, machine-readable audit trails, and zero-loss financial tracking.**

> **Production-quality pipelines with strict schema normalization, deterministic exception flagging, and local action queues.**

---

## 🚀 Overview

Vequil Agent provides a rigorous environment for answering the core question of venue finance: *Did yesterday's money actually settle the way it should have?* Unlike generalized RPA tools or fragile macro scripts, this framework treats payment reconciliation as a strict data engineering problem. It normalizes fragmented processor data into a unified ledger before flagging deterministic exceptions for human (or future agentic) review.

**Core Innovation:**
- Unified schema normalization across distinct payment processor exports
- Deterministic exception flagging isolating anomalies without ledger contamination
- Zero-dependency local visual dashboard for processor-level risk summaries
- Structural separation of deterministic matching and future LLM classification

**Key Features:**
- Time-aligned ingestion of synthetic Shift4, FreedomPay, and Amazon JWO exports
- Strict rules-based engine built on `pandas` for absolute auditability
- Machine-readable discrepancy outputs for downstream ERP integration
- Desktop-first B2B interface optimized for operational speed

**No live API integrations yet.** This is an engine-first prototype for offline reconciliation and pipeline development.

---

## 🎯 Scope and Philosophy

### What This Is
- **A deterministic reconciliation engine** - Built to parse, normalize, and match settled transactions against expected funds
- **A workflow modernization tool** - Replaces manual spreadsheet stitching with a single reproducible execution pipeline
- **A B2B system-of-record foundation** - Sits explicitly between point-of-sale processors and finance teams
- **An audit trail generator** - Prepares unresolved exceptions for an agentic review layer

### What This Is Not
- **Not a consumer app** - UI is desktop-first, designed for high-volume finance professionals
- **Not a black-box AI model** - Initial normalization and flagging are strictly rules-based to ensure absolute financial accuracy
- **Not a predictive analytics tool** - Focused entirely on historical settlement truth, not revenue forecasting
- **Not a live payment gateway** - Does not process transactions, only reconciles post-settlement data

---

## 🧠 Core Concepts

### The Reconciliation Wedge

Finance teams at large venues suffer from data fragmentation. Each processor provides different headers, different settlement timelines, and different exception codes. The framework enforces a strict model for handling this:

- **Normalize** - All synthetic exports map to a standardized schema (Timestamp, Ref ID, Amount, Processor, Status)
- **Match** - The engine scans for known, quantifiable states using deterministic rules
- **Flag** - Clean data pushes to `unified_ledger.csv`; anomalies isolate in `discrepancies.csv`

**Example:**
```python
# Raw Shift4: {"tx_ref": "A12", "amt": "15.00", "auth_status": "Y", "settled": "N"}
# Raw Amazon JWO: {"order_id": "A12", "total": 15.00, "captured": false}
# 
# Normalization: Both map to VequilStandard schema
# Flagging Engine: Detects `is_authorized == True` but `is_settled == False`
# Output: Sent to `discrepancies.csv` as UNSETTLED_FUNDS
```

This structural separation ensures that when an LLM is eventually introduced, it only evaluates highly specific edge cases, not the entire data pipeline.

---

## 🛠️ Installation

**Requirements:**
- Python 3.13 or above
- `pandas` (Core Engine)
- pip

### Install and Setup
```bash
git clone https://github.com/noahdonovan/clear-line.git
cd clear-line
pip install -r requirements.txt
```

---

## 📁 Project Structure
```
clear-line/
├── data/
│   ├── raw/                  # Drop zone for synthetic processor exports
│   │   ├── shift4_export.csv
│   │   ├── freedompay_export.csv
│   │   └── amazon_jwo_export.csv
│   └── output/               # Pipeline artifacts
│       ├── unified_ledger.csv
│       ├── discrepancies.csv
│       └── dashboard.json
│
├── src/
│   └── vequil/
│       ├── __init__.py
│       ├── pipeline.py       # Core execution and orchestration
│       ├── engine.py         # Pandas normalization and matching rules
│       ├── exceptions.py     # Deterministic flagging logic
│       └── server.py         # Local HTTP server for the action queue
│
├── web/
│   └── static/
│       ├── index.html        # Desktop-first B2B dashboard UI
│       ├── style.css
│       └── app.js            # Renders output/dashboard.json
│
├── docs/
│   └── roadmap.md            # Product sequence: prototype to pilot
│
├── tests/
│   ├── test_engine.py        # Schema validation checks
│   ├── test_exceptions.py    # Anomaly detection correctness
│   └── test_pipeline.py      # End-to-end integration tests
│
├── requirements.txt
└── README.md
```

---

## 🏃 Quick Start

### 1. Run the Reconciliation Pipeline

Drop your processor exports into `data/raw/`, then execute the engine to generate the latest ledger and discrepancy outputs:
```bash
cd /Users/noahdonovan/clear-line
PYTHONPATH=src python -m vequil.pipeline
```
*Outputs are immediately generated in `data/output/`.*

### 2. Launch the Action Queue Dashboard

Serve the generated data to the local browser dashboard for visual review and processor-level summaries:
```bash
cd /Users/noahdonovan/clear-line
PYTHONPATH=src python -m vequil.server
```

Then open `http://127.0.0.1:8000` in your browser.

---

## 🔬 Core Modules

### Engine Module (`vequil/engine.py`)

**Purpose:** High-speed data ingestion and schema normalization

**Key Components:**
- `DataIngestor`: Time-aligned, safe parsing of raw CSVs
- `SchemaNormalizer`: Maps disparate processor headers to `VequilStandard`
- `LedgerBuilder`: Compiles normalized data into a single master ledger

**Guarantees:**
- Strict type casting (e.g., currency conversion, timestamp timezone alignment)
- Forward-compatible handling of missing columns

### Exceptions Module (`vequil/exceptions.py`)

**Purpose:** Deterministic anomaly detection and flagging

**Standard Rules:**
```python
MISSING_AUTH      # Transaction settled but lacks authorization payload
DUPLICATE_REF     # Identical reference IDs across different settlement windows
UNSETTLED_FUNDS   # Authorized transactions missing from final processor batch
HIGH_VALUE_REVIEW # Transactions exceeding predefined venue risk thresholds
```

### Server Module (`vequil/server.py` & `web/static/`)

**Purpose:** Actionable UI layer for finance teams

**Philosophy:**
Zero-dependency Python standard library server rendering `dashboard.json` into a clean, scannable queue. Designed for rapid operational review rather than deep data exploration.

---

## 🧪 Testing and Validation

### Correctness Tests
```bash
# Run full test suite
pytest tests/

# Specific test categories
pytest tests/test_engine.py        # Normalization logic
pytest tests/test_exceptions.py    # Flagging accuracy
```

**Critical Tests:**
- **No data dropping**: Total raw rows must equal unified ledger rows + discrepancy rows
- **Deterministic output**: Same input CSVs produce identical JSON and CSV outputs
- **Idempotency**: Running the pipeline multiple times does not duplicate ledger entries

---

## 🚀 Advanced Usage

### Custom Processor Integration
```python
from vequil.engine import ProcessorMapper

class StripeMapper(ProcessorMapper):
    """Custom logic for a new POS processor."""
    
    def normalize(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """
        Map specific Stripe columns to Vequil standard.
        """
        return raw_data.rename(columns={
            'ch_id': 'reference_id',
            'created': 'timestamp',
            'amount_captured': 'amount_settled'
        })
```

---

## 🗺️ Roadmap

- [x] Core environment with synthetic data ingestion
- [x] Schema normalization framework (Shift4, FreedomPay, Amazon JWO)
- [x] Deterministic exception flagging rules
- [x] Local visual dashboard action queue
- [ ] Swap synthetic headers for live venue operating environments
- [ ] Add source-of-truth sales feeds (POS, ticketing, internal finance systems)
- [ ] Move rule configuration out of code into venue-specific JSON/YAML mappings
- [ ] Implement an agentic LLM classification step *strictly* for unresolved discrepancies
- [ ] Deploy to Google Cloud Run with proper IAM authentication and persistent Cloud Storage
- [ ] Connect downstream ERP integrations (NetSuite, Workday)

---

## 📜 License

Licensed under the MIT License. See `LICENSE` for details.

---

## 🤝 Contact & Acknowledgements

- **Maintainer:** Noah Donovan (nxd914@miami.edu)
- **Status:** Engine-First Prototype - Active Development