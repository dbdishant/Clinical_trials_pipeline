"""
transform.py
-------------
Normalizes raw ClinicalTrials.gov JSON records into a flat, clean schema,
and runs basic data quality checks (the kind a real data engineering
pipeline needs: completeness, type checks, dedup).
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import re


@dataclass
class CleanTrial:
    nct_id: str
    title: str
    status: str
    phase: Optional[str]
    condition: str
    brief_summary: str
    eligibility_criteria: str
    enrollment_count: Optional[int]
    start_date: Optional[str]
    completion_date: Optional[str]
    sponsor: Optional[str]


def _get(d: Dict[str, Any], path: List[str], default=None):
    """Safely walk a nested dict using a list of keys."""
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def normalize_record(raw: Dict[str, Any]) -> Optional[CleanTrial]:
    """Flatten one raw ClinicalTrials.gov study record into CleanTrial."""
    protocol = raw.get("protocolSection", {})

    nct_id = _get(protocol, ["identificationModule", "nctId"])
    if not nct_id:
        return None  # drop records missing the primary key

    title = _get(protocol, ["identificationModule", "briefTitle"], "")
    status = _get(protocol, ["statusModule", "overallStatus"], "UNKNOWN")
    phases = _get(protocol, ["designModule", "phases"], [])
    phase = ", ".join(phases) if phases else None

    conditions = _get(protocol, ["conditionsModule", "conditions"], [])
    condition = ", ".join(conditions) if conditions else "UNKNOWN"

    brief_summary = _get(protocol, ["descriptionModule", "briefSummary"], "")
    eligibility = _get(protocol, ["eligibilityModule", "eligibilityCriteria"], "")

    enrollment = _get(protocol, ["designModule", "enrollmentInfo", "count"])
    try:
        enrollment_count = int(enrollment) if enrollment is not None else None
    except (ValueError, TypeError):
        enrollment_count = None

    start_date = _get(protocol, ["statusModule", "startDateStruct", "date"])
    completion_date = _get(protocol, ["statusModule", "completionDateStruct", "date"])
    sponsor = _get(protocol, ["sponsorCollaboratorsModule", "leadSponsor", "name"])

    return CleanTrial(
        nct_id=nct_id,
        title=title.strip(),
        status=status,
        phase=phase,
        condition=condition,
        brief_summary=re.sub(r"\s+", " ", brief_summary).strip(),
        eligibility_criteria=re.sub(r"\s+", " ", eligibility).strip(),
        enrollment_count=enrollment_count,
        start_date=start_date,
        completion_date=completion_date,
        sponsor=sponsor,
    )


def transform_records(raw_records: List[Dict[str, Any]]) -> List[CleanTrial]:
    cleaned = []
    seen_ids = set()
    for raw in raw_records:
        rec = normalize_record(raw)
        if rec is None:
            continue
        if rec.nct_id in seen_ids:
            continue  # dedup
        seen_ids.add(rec.nct_id)
        cleaned.append(rec)
    return cleaned


# ---------------------------------------------------------------------------
# Data quality checks
# ---------------------------------------------------------------------------

def run_quality_checks(records: List[CleanTrial]) -> Dict[str, Any]:
    """
    Returns a small data-quality report: completeness rates and flagged
    records. This is the kind of monitoring step the JD calls out
    ('implement quality control and monitoring processes').
    """
    total = len(records)
    if total == 0:
        return {"total_records": 0, "issues": ["No records to check"]}

    missing_summary = sum(1 for r in records if not r.brief_summary)
    missing_eligibility = sum(1 for r in records if not r.eligibility_criteria)
    missing_enrollment = sum(1 for r in records if r.enrollment_count is None)
    unknown_condition = sum(1 for r in records if r.condition == "UNKNOWN")

    report = {
        "total_records": total,
        "missing_brief_summary_pct": round(100 * missing_summary / total, 1),
        "missing_eligibility_pct": round(100 * missing_eligibility / total, 1),
        "missing_enrollment_pct": round(100 * missing_enrollment / total, 1),
        "unknown_condition_pct": round(100 * unknown_condition / total, 1),
    }
    return report


def records_to_dicts(records: List[CleanTrial]) -> List[Dict[str, Any]]:
    return [asdict(r) for r in records]
