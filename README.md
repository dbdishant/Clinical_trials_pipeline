# Clinical Trial Data Pipeline + LLM Plain-Language Summarizer

A small end-to-end data engineering project: it pulls clinical trial
records from the public [ClinicalTrials.gov](https://clinicaltrials.gov/data-api/api)
API, cleans and validates them, loads them into a database, and uses an
LLM (Claude) to turn dense regulatory eligibility text into plain-language
summaries a patient or non-specialist could actually read.

## Why this project

Clinical trial listings are public, but they're written in dense
regulatory language that's hard for patients and even non-specialist
staff to parse. This pipeline automates the unglamorous data engineering
work (fetch → clean → validate → store) and adds an AI layer that makes
the data more usable downstream — the same pattern used in real
healthcare/pharma data platforms.

## Architecture

```
ClinicalTrials.gov API
        |
        v
  fetch_trials.py   -->  data/raw_trials.json   (raw extract)
        |
        v
  transform.py       -->  cleaned, deduped, validated records
        |                  + data quality report (% missing fields)
        v
  db.py              -->  SQLite: trials table
        |
        v
  summarize.py        -->  Claude API: plain-language summary +
        |                   plain-language eligibility bullets
        v
  db.py               -->  SQLite: trial_summaries table
        |
        v
  main.py export       -->  output/trial_report.csv  (stakeholder-ready)
```

## What it demonstrates

| JD requirement | Where it shows up |
|---|---|
| Pull/manipulate data via APIs | `fetch_trials.py` calls the ClinicalTrials.gov REST API |
| Build/maintain ETL pipelines | `main.py` orchestrates fetch → clean → load → summarize → export |
| Quality control & monitoring | `transform.py::run_quality_checks()` reports missing-field rates |
| Documentation of pipeline/configs | This README + inline docstrings in every module |
| LLM / AI applied to a healthcare-adjacent dataset | `summarize.py` uses Claude to translate clinical trial text into plain language |

## Project layout

```
clinical-trials-pipeline/
├── data/
│   └── sample_trials.json   # bundled sample data (5 type-2-diabetes trials) for offline demo
├── output/
│   └── trial_report.csv     # generated after running the pipeline
├── src/
│   ├── fetch_trials.py      # API extraction
│   ├── transform.py         # cleaning, dedup, data quality checks
│   ├── db.py                # SQLite storage layer
│   ├── summarize.py         # Claude-powered plain-language summarization (paid)
│   ├── summarize_ollama.py  # local, free plain-language summarization via Ollama
│   └── main.py              # CLI orchestrator
├── requirements.txt
└── README.md
```

## Setup

This project supports two LLM backends:

- **Ollama (default, free, local, no signup)** — runs a small open-source model on your own machine.
- **Anthropic API (Claude, paid)** — higher quality summaries, needs an API key with credit.

### Option A: Ollama (free)

1. Install Ollama: https://ollama.com/download
2. Pull a small model (one-time, ~2GB download):
   ```bash
   ollama pull llama3.2
   ```
3. Make sure Ollama is running (it usually starts automatically after install;
   if not, run `ollama serve` in a separate terminal).
4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

No API key, no signup, no cost — everything runs on your machine.

### Option B: Anthropic API (paid, higher quality)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
```

## Usage

Run the full pipeline with the free local model (default):

```bash
python -m src.main --use-sample
```

Run with Claude instead, if you have an API key:

```bash
python -m src.main --use-sample --backend anthropic
```

Run against live data from ClinicalTrials.gov:

```bash
python -m src.main --condition "type 2 diabetes" --max-records 50
```

Run the pipeline without calling any LLM (useful for testing the data
engineering steps in isolation):

```bash
python -m src.main --use-sample --skip-llm
```

Each run prints a data quality report to the console, e.g.:

```
STEP 3: Data Quality Check
============================================================
  total_records: 5
  missing_brief_summary_pct: 0.0
  missing_eligibility_pct: 0.0
  missing_enrollment_pct: 0.0
  unknown_condition_pct: 0.0
```

And produces `output/trial_report.csv` — a flat file with every trial,
its key fields, and (if the LLM step ran) a plain-language summary and
eligibility breakdown, ready to hand to a non-technical stakeholder.

## Example output (from a live Claude summarization run)

> **Trial:** Safety and Efficacy of a Novel GLP-1 Agonist in Type 2 Diabetes
>
> **Plain-language summary:** This trial tests whether a once-weekly
> injectable medication helps adults with type 2 diabetes who are
> overweight lower their blood sugar more effectively than a placebo.
>
> **Eligibility (plain language):**
> - Must be 18 or older
> - Body Mass Index (BMI) of 27 or higher
> - Blood sugar (HbA1c) between 7.5% and 11.0%
> - Already taking metformin for at least 3 months
> - Cannot have a history of pancreatitis or thyroid cancer

## Notes / honest limitations

- This is a demo project, not a production healthcare system — there's
  no PHI involved; all data comes from the public ClinicalTrials.gov
  registry.
- The LLM summaries are for general accessibility, not medical advice —
  the system prompt in `summarize.py` makes that boundary explicit.
- SQLite is used for portability. The schema in `db.py` would map
  directly onto Postgres/MySQL for a larger deployment.
