# TowerPulse AI 🗼📊

An enterprise natural-language query engine over structured **Telecom Tower Infrastructure** sales and operational metrics (`circle`, `site_id`, `tenant`, `colocation_count`, `target_colocations`, `uptime_pct`, `sla_target_pct`, `energy_consumption_kwh`, `energy_budget_kwh`, `month`). Automatically flags SLA breaches, colocation shortfalls, and energy overruns while strictly enforcing a deterministic validation layer to prevent LLM hallucinations and SQL injection.

---

## 🎯 The Problem This Solves
Traditional Business Intelligence (BI) dashboards require manual filtering and slice-and-dice aggregations. When executives ask conversational questions (e.g., *"Which tower sites in Delhi breached SLA uptime in August 2026?"*), standard BI tools require analyst intervention.

While LLMs can translate natural language to SQL, raw LLM outputs pose major production risks:
- **Hallucinated Columns/Tables**: LLMs may reference non-existent fields (e.g., `revenue`, `sales_rep`), causing silent errors or misleading results.
- **SQL Injection Risks**: Malicious or unintended prompts might attempt state-mutating operations (`DELETE`, `DROP`).

**TowerPulse AI** pairs an LLM query engine with a **zero-trust deterministic validation layer** and **dynamic multi-vector telecom exception analytics**.

---

## 🏗️ Architecture

```
[ User Query ]
      │
      ▼
[ Natural Language to SQL (llm.py) ] ◄── Few-Shot Prompting (Groq / OpenAI)
      │
      ▼
[ Deterministic Validation (validate.py) ] ──(Fails)──► Retry Loop (Max 2 Attempts)
      │ (Passes)                                              │
      ▼                                                       ▼
[ SQLite Execution (db.py) ]                           [ Error Alert ]
      │
      ▼
[ Exception Flagging Engine (exceptions.py) ] ◄── Multi-Vector Exception Rules
      │
      ▼
[ Streamlit Dashboard (app.py) ]
```

### Key Architectural Highlights:
> **LLM output is never executed without passing through a deterministic validation layer that checks it against the real schema — this prevents hallucinated columns/tables from silently corrupting results.**

1. **Data Layer (`db.py`)**: SQLite database (`sales.db`) seeded with 969 realistic telecom tower infrastructure records across 10 circles and 6 months.
2. **NL-to-SQL Layer (`llm.py`)**: Converts natural language into SQLite `SELECT` statements using Groq (LLaMA3 / GPT-OSS) or OpenAI with few-shot examples.
3. **Deterministic Validation Layer (`validate.py`)**:
   - Enforces `SELECT`-only operations (blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`).
   - Verifies every table and column against live schema.
   - Blocks comments (`--`, `/*`) and multi-statement execution (`;`).
   - Supports self-correction retry with specific error feedback appended to the LLM prompt.
4. **Exception/Threshold Logic (`exceptions.py`)**: Multi-vector exception rules (SLA Uptime Breaches, Colocation Shortfalls, Energy Budget Overruns).
5. **Dashboard Layer (`app.py`)**: Interactive Streamlit UI featuring Plotly charts, live sliders, metrics, query status badges, and CSV export.

---

## 📂 Project Structure

```
ai_sales_exception_reporter/
├── db.py               # SQLite database schema initialization & query runner (tower_sites)
├── llm.py              # LLM natural-language-to-SQL pipeline & retry handler
├── validate.py         # Deterministic SQL validation engine (anti-hallucination & injection)
├── exceptions.py       # Multi-vector telecom exception detection logic
├── app.py              # Interactive Streamlit dashboard UI (TowerPulse AI)
├── generate_tower_data.py # Reproducible synthetic telecom tower dataset generator
├── tower_sites.csv     # Telecom tower infrastructure dataset (969 rows)
├── requirements.txt    # Dependencies (Streamlit, Pandas, Groq, OpenAI, SQLParse, Plotly)
├── .env                # Local environment secrets (GROQ_API_KEY)
├── .env.example        # Environment variable template
├── .gitignore          # Excludes sensitive files from git
└── README.md           # Documentation
```

---

## 🚀 How to Run Locally

### 1. Prerequisites
Ensure Python 3.11+ is installed.

### 2. Install Dependencies
```bash
cd ai_sales_exception_reporter
pip install -r requirements.txt
```

### 3. Environment Setup (API Key)
Your Groq API key is configured in `.env`:
```env
GROQ_API_KEY=gsk_18hXjqt...
GROQ_MODEL=openai/gpt-oss-120b
```

### 4. Launch Streamlit Application
```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.
