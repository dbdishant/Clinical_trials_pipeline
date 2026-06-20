"""
main.py
-------
Orchestrates the full pipeline:
  1. Fetch raw trial data (from ClinicalTrials.gov, or a bundled sample file)
  2. Clean / normalize / dedupe
  3. Run data quality checks
  4. Load into SQLite
  5. Summarize with Claude (plain-language summary + eligibility points)
  6. Export a final report (CSV) for non-technical stakeholders

Usage:
    python -m src.main --condition "type 2 diabetes" --max-records 50
    python -m src.main --use-sample        # run offline with bundled sample data
    python -m src.main --use-sample --skip-llm   # run pipeline without calling Claude
"""

import argparse
import csv
import json
from pathlib import Path

from src import fetch_trials, transform, db as db_module


def load_sample(path: str = "data/sample_trials.json"):
    with open(path) as f:
        return json.load(f)


def export_report(db_path: str, out_path: str) -> None:
    rows = db_module.get_all_with_summaries(db_path)
    if not rows:
        print("No data to export.")
        return

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="", encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} rows to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Clinical trial data pipeline + LLM summarizer")
    parser.add_argument("--condition", default="type 2 diabetes")
    parser.add_argument("--max-records", type=int, default=50)
    parser.add_argument("--use-sample", action="store_true", help="Use bundled sample data instead of live API")
    parser.add_argument("--skip-llm", action="store_true", help="Skip the summarization step")
    parser.add_argument(
        "--backend",
        choices=["anthropic", "ollama"],
        default="ollama",
        help="Which LLM backend to use for summarization (default: ollama, which is free/local)",
    )
    parser.add_argument("--db", default="data/trials.db")
    parser.add_argument("--report-out", default="output/trial_report.csv")
    args = parser.parse_args()

    print("=" * 60)
    print("STEP 1: Fetch")
    print("=" * 60)
    if args.use_sample:
        raw = load_sample()
        print(f"Loaded {len(raw)} sample records from data/sample_trials.json")
    else:
        raw = fetch_trials.fetch_trials(args.condition, args.max_records)
        fetch_trials.save_raw(raw, "data/raw_trials.json")
        print(f"Fetched {len(raw)} live records for '{args.condition}'")

    print("\n" + "=" * 60)
    print("STEP 2: Clean & Transform")
    print("=" * 60)
    cleaned = transform.transform_records(raw)
    print(f"Cleaned to {len(cleaned)} unique, valid records (deduped + dropped malformed)")

    print("\n" + "=" * 60)
    print("STEP 3: Data Quality Check")
    print("=" * 60)
    report = transform.run_quality_checks(cleaned)
    for k, v in report.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("STEP 4: Load into SQLite")
    print("=" * 60)
    db_module.init_db(args.db)
    n = db_module.upsert_trials(transform.records_to_dicts(cleaned), args.db)
    print(f"Loaded {n} records into {args.db}")

    if not args.skip_llm:
        print("\n" + "=" * 60)
        print(f"STEP 5: Summarize with LLM (backend: {args.backend})")
        print("=" * 60)
        if args.backend == "ollama":
            from src import summarize_ollama as summarize_module
        else:
            from src import summarize as summarize_module
        n_summarized = summarize_module.summarize_pending_trials(args.db)
        print(f"Generated {n_summarized} plain-language summaries")
    else:
        print("\n(Skipping LLM summarization step — --skip-llm was set)")

    print("\n" + "=" * 60)
    print("STEP 6: Export Report")
    print("=" * 60)
    export_report(args.db, args.report_out)


if __name__ == "__main__":
    main()
