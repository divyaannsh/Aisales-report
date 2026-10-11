# TowerPulse AI 🗼

> A working proof-of-concept that replaces manual Power BI exception reporting for telecom tower infrastructure with a natural-language AI query engine — built specifically around Indus Towers' operational KPIs.

---

## What this project does (plain English)

Right now, when a business analyst wants to know *"which tower sites in Delhi missed their SLA last month?"*, they open Power BI, apply 3–4 filters, wait, copy the result into an email, and send it to the ops manager. That takes 20–30 minutes every morning.

This project lets anyone ask that same question in plain English — and get an exception report back in seconds, automatically.

**The 5-step flow:**

```
You ask a question in plain English
        ↓
AI Agent translates it to a database query
        ↓
Validation layer checks the query is safe (no deletes, no hallucinated columns)
        ↓
Database runs the query and returns raw data
        ↓
Exception engine flags SLA breaches · energy overruns · colocation shortfalls
        ↓
Dashboard shows results + AI summary + ₹ business impact
```

---

## The 3 problems it solves

| Problem today (manual Power BI) | What this does instead |
|---|---|
| Analyst spends 20–30 min every morning filtering dashboards | One question → automatic exception report |
| LLMs can hallucinate column names and run wrong queries silently | Validation layer blocks any query that references a column that doesn't exist |
| Exceptions are just numbers — no context on *why* or *what next* | AI-generated executive summary in business language after every query |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Question                         │
│   "Which Delhi sites breached SLA uptime in Aug 2026?"      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  LLM Engine │  (Groq / OpenAI)
                    │  NL → SQL   │  Few-shot prompted
                    └──────┬──────┘
                           │
              ┌────────────▼─────────────┐
              │   Validation Layer        │
              │  ✓ SELECT-only guard      │
              │  ✓ Schema column check    │
              │  ✓ Anti-injection shield  │
              └────────────┬─────────────┘
                    Pass   │   Fail → retry (max 2x) → block
                           │
                    ┌──────▼──────┐
                    │  SQLite DB  │  (tower_sites — 575 records)
                    └──────┬──────┘
                           │
              ┌────────────▼──────────────────────┐
              │      Exception Engine              │
              │  · SLA Uptime Breach (< 95%)       │
              │  · Colocation Shortfall            │
              │  · Energy Budget Overrun (> 110%)  │
              └────────────┬──────────────────────┘
                           │
        ┌──────────────────▼────────────────────────┐
        │            Dashboard Output                │
        │  · AI Executive Summary (board-ready)      │
        │  · ₹ Business Impact (energy, SLA, coloc)  │
        │  · Month-over-Month trend chart            │
        │  · Circle hotspot treemap                  │
        │  · Flagged records table + CSV export      │
        └────────────────────────────────────────────┘
```

---

## Dataset

Synthetic data modelled on Indus Towers' operational structure:

- **575 records (60 sites, 10 circles, 6 months, multiple tenants per site)**
- Circles: Delhi, Mumbai, UP-East, UP-West, Punjab, Maharashtra, Rajasthan, Karnataka, Tamil Nadu, West Bengal
- Tenants: Airtel, Reliance Jio, Vodafone Idea, BSNL
- KPIs: uptime %, SLA target, colocation count vs target, energy consumption vs budget

---

## How to run

### 1. Clone and install
```bash
git clone <repo-url>
cd ai_sales_exception_reporter
pip install -r requirements.txt
```

### 2. Set your API key
```bash
cp .env.example .env
# Open .env and add your Groq API key:
# GROQ_API_KEY=your_key_here
```

Get a free Groq key at [console.groq.com](https://console.groq.com)

### 3. Run
```bash
streamlit run app.py
```

Opens at `http://localhost:8501`

> **No API key?** The app has an offline fallback mode that uses keyword-based SQL generation. Full LLM features need a Groq key.

---

## Demo script (for interviews / presentations)

Run these 4 tests in order — each one makes a specific point:

**1. Normal query** — shows the core value
> *"Which tower sites in Delhi breached SLA uptime in August 2026?"*

Shows only sites that actually breached the threshold. No manual filtering.

**2. Slider adjustment** — shows adaptability
> Move the SLA threshold slider from 95% to 97% and watch the flagged list update live.

Makes the point: *"thresholds change — the system adapts without rebuilding anything."*

**3. Injection attack** — shows the safety layer
> Type: `delete all rows from tower_sites`

Validation blocks it. Nothing gets executed. This is the strongest demo moment.

**4. Hallucination test** — shows why validation matters
> Type: *"Show revenue by site"* (column `revenue` doesn't exist)

Validation rejects the LLM's generated SQL and retries. Numbers only come from the actual database — the LLM never makes up a figure.

---

## How this scales to a real Indus Towers setup

This project is the **base layer**. The planned production architecture adds:

```
User (Teams / scheduled morning report)
        ↓
   AI Agent (orchestrator LLM)
        ↓
   MCP Tools:
     · Power BI semantic model (read-only — reuses existing KPI definitions)
     · RAG over documents (SLA contracts, SOPs, incident tickets)
     · Report/alert tool (email, Teams message)
        ↓
   Guardrail layer (same as TowerPulse validation)
        ↓
   Output: exception report + root cause + suggested action
```

**The key point:** the `validate_sql + execute_query` functions in this project become the MCP tool. The LLM doesn't change — only the tool interface does. This means the existing Power BI semantic model stays in place; nothing gets replaced, only augmented.

**Rollout plan (what I'd propose in the first 90 days):**
- **Day 1–30:** One report automated (SLA exceptions), read-only, validated against manual output
- **Day 30–60:** Add RAG over SLA contracts and incident tickets for root-cause context
- **Day 60–90:** Scheduled morning digest + additional KPIs (energy, tenancy)

---

## Accuracy & Safety Evaluation (`eval.py`)

To measure Text-to-SQL reliability honestly without hand-waving, the project includes an automated 25-question evaluation suite ([eval_questions.json](file:///Users/divyanshsrivastava/Documents/baud/ai_sales_exception_reporter/eval_questions.json)) tested via [eval.py](file:///Users/divyanshsrivastava/Documents/baud/ai_sales_exception_reporter/eval.py):

- **20 Normal Operational Queries:** SLA uptime breaches by circle/month, colocation shortfalls, energy overruns, counts, averages, and group-by queries.
- **5 Adversarial Security Tests:** DDL/DML mutations (`DELETE`, `DROP`, `UPDATE`), comment injection (`--`), and hallucinated columns (`revenue`).

### Benchmark Results
- **Strict SQL Semantic Accuracy:** **86.7% average** (Run 1: 85.0%, Run 2: 85.0%, Run 3: 90.0% against hand-written Gold SQL).
- **Adversarial Safety Rate:** **100% neutralized** (12/15 refused upfront via `UNSUPPORTED:`, 3/15 sanitized to safe SELECT; 0 mutations executed).
- **Query Latency:** **Median: ~2.0s (1,969 ms)**, **P95: ~8.4s** on `openai/gpt-oss-120b` (`reasoning_effort="low"`).
- **Flakiness:** **4.0%** (1 of 25 queries varied across 3 independent runs).
- **Dual-Layer Security:** 
  1. Token-level validation (`validate.py` via `sqlparse` + `EXPLAIN`) blocks non-SELECT statements, dangling clauses, and unapproved columns.
  2. Operating system-level read-only mode (`sqlite3 file:sales.db?mode=ro` in `db.py`) blocks writes at the SQLite C-engine level.
- **Query Audit Logging:** Every query, generated SQL, validation status, rows returned, and execution latency is automatically recorded in both SQLite (`query_audit_log`) and `audit_log.jsonl`.

Run the evaluation yourself:
```bash
python eval.py
```
Outputs complete breakdown to `eval_report.md`.

---

## Daily Operations Digest CLI (`digest.py`)

A deterministic, zero-LLM morning reporting script that queries latest month exceptions via SQL and generates an executive briefing:

```bash
python digest.py
```
- Outputs `digest_YYYY-MM-DD.md` (formatted markdown briefing for Teams/Email).
- Outputs `digest_exceptions_YYYY-MM-DD.csv` (complete list of flagged sites).

---

## Project files

| File | What it does |
|---|---|
| `app.py` | Streamlit command center — GIS map, tabs, What-If sandbox, Teams dispatcher |
| `llm.py` | Converts plain English to SQL using Groq/OpenAI + Executive Summary generator |
| `validate.py` | Deterministic token-level validator (sqlparse + EXPLAIN) blocking unsafe SQL and hallucinated columns |
| `db.py` | SQLite setup, read-only connection (`mode=ro`), and query audit logging |
| `digest.py` | Deterministic daily exception digest CLI (Markdown + CSV export) |
| `eval.py` | 25-question tri-run benchmark measuring Text-to-SQL accuracy, flakiness, and security |
| `test_validator.py` | Standalone deterministic unit tests (25 test cases, 0 LLM calls) for validator rules |
| `eval_questions.json` | Test suite of 20 operational + 5 adversarial benchmark questions |
| `exceptions.py` | Flags SLA breaches, colocation shortfalls, energy overruns + Prescriptive SOP engine |
| `generate_tower_data.py` | Creates synthetic telecom dataset calibrated to Indus KPIs (~1.62x tenancy, ~99.9% uptime) |
| `tower_sites.csv` | The calibrated dataset (575 records across 60 sites and 10 circles) |


