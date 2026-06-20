"""
fetch_trials.py
----------------
Pulls clinical trial records from the public ClinicalTrials.gov API (v2).
No API key required - it's a free, public government API.

API docs: https://clinicaltrials.gov/data-api/api
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any

import requests

API_BASE = "https://clinicaltrials.gov/api/v2/studies"
PAGE_SIZE = 50


def fetch_trials(condition: str, max_records: int = 200) -> List[Dict[str, Any]]:
    """
    Fetch trial records for a given condition (e.g. 'type 2 diabetes').
    Handles pagination via the API's nextPageToken.
    """
    records: List[Dict[str, Any]] = []
    next_token = None

    while len(records) < max_records:
        params = {
            "query.cond": condition,
            "pageSize": PAGE_SIZE,
            "format": "json",
        }
        if next_token:
            params["pageToken"] = next_token

        resp = requests.get(API_BASE, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        studies = payload.get("studies", [])
        records.extend(studies)

        next_token = payload.get("nextPageToken")
        if not next_token or not studies:
            break

        time.sleep(0.3)  # be polite to the public API

    return records[:max_records]


def save_raw(records: List[Dict[str, Any]], out_path: str) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch trials from ClinicalTrials.gov")
    parser.add_argument("--condition", default="type 2 diabetes")
    parser.add_argument("--max-records", type=int, default=100)
    parser.add_argument("--out", default="data/raw_trials.json")
    args = parser.parse_args()

    print(f"Fetching trials for condition: {args.condition!r}")
    trials = fetch_trials(args.condition, args.max_records)
    save_raw(trials, args.out)
    print(f"Saved {len(trials)} raw trial records to {args.out}")
