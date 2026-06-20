"""
summarize.py
------------
Uses Claude (Anthropic API) to turn dense clinical trial text - brief
summaries and eligibility criteria, which are written in dense regulatory
language - into plain-language summaries a patient or non-specialist
stakeholder could actually read.

Requires an ANTHROPIC_API_KEY environment variable.
Install: pip install anthropic
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are a clinical research assistant that explains clinical trials "
    "in plain, accessible English for a general audience. You are not "
    "providing medical advice. Be factual and concise."
)

PROMPT_TEMPLATE = """Here is a clinical trial record:

Title: {title}
Condition(s): {condition}
Phase: {phase}
Status: {status}

Brief summary (from ClinicalTrials.gov):
{brief_summary}

Eligibility criteria (raw, from ClinicalTrials.gov):
{eligibility_criteria}

Do two things:
1. Write a 2-3 sentence plain-language summary of what this trial is testing and why it matters.
2. List the 3-5 most important eligibility points in plain language, as a short bulleted list.

Respond in this exact format:
SUMMARY: <your summary>
ELIGIBILITY: <your bulleted list, each point on its own line starting with "- ">
"""


def summarize_trial(trial: Dict[str, Any], client: anthropic.Anthropic) -> Dict[str, str]:
    prompt = PROMPT_TEMPLATE.format(
        title=trial.get("title", ""),
        condition=trial.get("condition", ""),
        phase=trial.get("phase") or "Not specified",
        status=trial.get("status", ""),
        brief_summary=trial.get("brief_summary") or "Not provided.",
        eligibility_criteria=(trial.get("eligibility_criteria") or "Not provided.")[:3000],
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")

    plain_summary, eligibility_points = _parse_response(text)
    return {"plain_summary": plain_summary, "key_eligibility_points": eligibility_points}


def _parse_response(text: str) -> tuple:
    summary, eligibility = "", ""
    if "SUMMARY:" in text and "ELIGIBILITY:" in text:
        summary_part = text.split("SUMMARY:")[1].split("ELIGIBILITY:")[0].strip()
        eligibility_part = text.split("ELIGIBILITY:")[1].strip()
        summary, eligibility = summary_part, eligibility_part
    else:
        summary = text.strip()  # fallback: keep raw text rather than lose it
    return summary, eligibility


def summarize_pending_trials(db_path: str = "data/trials.db") -> int:
    """Pulls every trial without a summary yet, summarizes it, and saves it."""
    from . import db as db_module  # local import to avoid circular import at module load

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Get a key at https://console.anthropic.com and export it before running."
        )

    client = anthropic.Anthropic(api_key=api_key)
    pending = db_module.get_trials_missing_summary(db_path)

    count = 0
    for trial in pending:
        result = summarize_trial(trial, client)
        db_module.save_summary(
            nct_id=trial["nct_id"],
            plain_summary=result["plain_summary"],
            key_eligibility_points=result["key_eligibility_points"],
            generated_at=datetime.now(timezone.utc).isoformat(),
            db_path=db_path,
        )
        count += 1
        print(f"  Summarized {trial['nct_id']} ({trial['title'][:60]}...)")

    return count
