"""
db.py
-----
Lightweight SQLite storage layer for cleaned trial records and their
LLM-generated summaries. SQLite is used here so the project runs anywhere
with zero setup; the schema maps cleanly onto Postgres/MySQL if needed.
"""

import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    nct_id TEXT PRIMARY KEY,
    title TEXT,
    status TEXT,
    phase TEXT,
    condition TEXT,
    brief_summary TEXT,
    eligibility_criteria TEXT,
    enrollment_count INTEGER,
    start_date TEXT,
    completion_date TEXT,
    sponsor TEXT
);

CREATE TABLE IF NOT EXISTS trial_summaries (
    nct_id TEXT PRIMARY KEY,
    plain_summary TEXT,
    key_eligibility_points TEXT,
    generated_at TEXT,
    FOREIGN KEY (nct_id) REFERENCES trials (nct_id)
);
"""


@contextmanager
def get_connection(db_path: str = "data/trials.db"):
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = "data/trials.db") -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def upsert_trials(records: List[Dict[str, Any]], db_path: str = "data/trials.db") -> int:
    cols = [
        "nct_id", "title", "status", "phase", "condition", "brief_summary",
        "eligibility_criteria", "enrollment_count", "start_date",
        "completion_date", "sponsor",
    ]
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)

    with get_connection(db_path) as conn:
        cur = conn.cursor()
        for rec in records:
            values = [rec.get(c) for c in cols]
            cur.execute(
                f"INSERT OR REPLACE INTO trials ({col_list}) VALUES ({placeholders})",
                values,
            )
        conn.commit()
        return len(records)


def save_summary(
    nct_id: str,
    plain_summary: str,
    key_eligibility_points: str,
    generated_at: str,
    db_path: str = "data/trials.db",
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO trial_summaries
                (nct_id, plain_summary, key_eligibility_points, generated_at)
            VALUES (?, ?, ?, ?)
            """,
            (nct_id, plain_summary, key_eligibility_points, generated_at),
        )
        conn.commit()


def get_trials_missing_summary(db_path: str = "data/trials.db") -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT t.* FROM trials t
            LEFT JOIN trial_summaries s ON t.nct_id = s.nct_id
            WHERE s.nct_id IS NULL
            """
        )
        return [dict(row) for row in cur.fetchall()]


def get_all_with_summaries(db_path: str = "data/trials.db") -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT t.*, s.plain_summary, s.key_eligibility_points
            FROM trials t
            LEFT JOIN trial_summaries s ON t.nct_id = s.nct_id
            """
        )
        return [dict(row) for row in cur.fetchall()]
