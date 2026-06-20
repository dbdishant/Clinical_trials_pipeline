"""
summarize_ollama.py
--------------------
Free, fully local alternative to summarize.py — uses Ollama instead of the
Anthropic API, so this runs with zero cost and no API key.

Setup (one-time):
  1. Install Ollama: https://ollama.com/download
  2. Pull a small model:   ollama pull llama3.2
  3. Make sure Ollama is running (it runs as a background service after install,
     or start it manually with: ollama serve)

That's it - no signup, no API key, no internet access needed once the model
is downloaded.
"""

import requests
from datetime import datetime, timezone
from typing import Dict, Any

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"
# MODEL = "llama3.2"  # swap for any model you've pulled, e.g. "mistral" or "phi3"

SYSTEM_PROMPT = (
    "You are a clinical research assistant that explains clinical trials "
    "in plain, accessible English for a general audience. You are not "
    "providing medical advice. Be factual and concise."
)

PROMPT_TEMPLATE = """{system}

Here is a clinical trial record:

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


def summarize_trial(trial: Dict[str, Any]) -> Dict[str, str]:
    prompt = PROMPT_TEMPLATE.format(
        system=SYSTEM_PROMPT,
        title=trial.get("title", ""),
        condition=trial.get("condition", ""),
        phase=trial.get("phase") or "Not specified",
        status=trial.get("status", ""),
        brief_summary=trial.get("brief_summary") or "Not provided.",
        eligibility_criteria=(trial.get("eligibility_criteria") or "Not provided.")[:3000],
    )

    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False},
        timeout=300,
    )
    response.raise_for_status()
    text = response.json().get("response", "")

    plain_summary, eligibility_points = _parse_response(text)
    return {"plain_summary": plain_summary, "key_eligibility_points": eligibility_points}


def _parse_response(text: str) -> tuple:
    summary, eligibility = "", ""
    if "SUMMARY:" in text and "ELIGIBILITY:" in text:
        summary_part = text.split("SUMMARY:")[1].split("ELIGIBILITY:")[0].strip()
        eligibility_part = text.split("ELIGIBILITY:")[1].strip()
        summary, eligibility = summary_part, eligibility_part
    else:
        summary = text.strip()
    return summary, eligibility


def summarize_pending_trials(db_path: str = "data/trials.db") -> int:
    """Pulls every trial without a summary yet, summarizes it locally, and saves it."""
    from . import db as db_module

    # quick connectivity check with a clear error message
    try:
        requests.get("http://localhost:11434", timeout=3)
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Could not reach Ollama at http://localhost:11434. "
            "Make sure Ollama is installed and running: see https://ollama.com/download, "
            "then run 'ollama pull llama3.2' and try again."
        )

    pending = db_module.get_trials_missing_summary(db_path)

    count = 0
    for trial in pending:
        result = summarize_trial(trial)
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
