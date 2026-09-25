"""The new copy path pipeline: cleaned pack -> extract -> write -> lint -> file.

    from src import copypath
    report = copypath.run_pipeline(leads)

This orchestrates the stages the task names:
1. Cleaned pack (nav chrome stripped)
2. Extraction (Groq gpt-oss-120b)
3. Writing (BLOCKED - no Anthropic key/adapter)
4. Lint (copylint + batch subject_faults)
5. File (review file builder)

## WHAT THIS DOES NOT DO

- It does not write prompts. Prompts live in `copyprompts.py`.
- It does not call Anthropic. The writing step is blocked and reports so.
- It does not write to `work/queue.jsonl` or `work/campaigns.jsonl`.
- It does not send anything.

## THE BATCH SUBJECT CHECK

`copyprompts.subject_faults` is run across the WHOLE file with a shared
`seen` set, so duplicates are caught batch-wide rather than per lead.
This is the operator's subject rules made mechanical.
"""
import json
import os
import time

from . import copyprompts, copyextract, packcleaner


def clean_packs(leads):
    """Stage 1: strip nav chrome from every lead's sources.

    Returns (cleaned_leads, metrics) where metrics carries the before/after
    character counts.
    """
    cleaned = []
    total_before = 0
    total_after = 0
    leads_with_any_sources = 0

    for lead in leads:
        sources = lead.get("sources") or []
        if sources:
            leads_with_any_sources += 1
        cleaned_sources, before, after = packcleaner.clean_sources(sources)
        total_before += before
        total_after += after
        cleaned.append({**lead, "sources": cleaned_sources,
                        "_raw_chars": before, "_clean_chars": after})

    n = max(leads_with_any_sources, 1)
    metrics = {
        "leads": len(leads),
        "leads_with_sources": leads_with_any_sources,
        "total_chars_before": total_before,
        "total_chars_after": total_after,
        "mean_chars_before": round(total_before / n, 1),
        "mean_chars_after": round(total_after / n, 1),
        "reduction_pct": round(
            (1 - total_after / max(total_before, 1)) * 100, 1),
    }
    return cleaned, metrics


def extract_facts(leads, model=None):
    """Stage 3: extract facts via Groq.

    Returns (results, metrics) where results maps lead_id to extraction output.
    """
    return copyextract.extract_batch(leads, model=model)


def batch_subject_check(writers_output):
    """Stage 5a: run `subject_faults` across the whole file with a shared
    `seen` set.

    `writers_output` is a list of {lead_id, subject, ...} dicts.
    Returns a list of {lead_id, faults} for every lead that has faults.
    """
    seen = set()
    faults = []
    for entry in writers_output:
        lead_id = entry.get("lead_id") or entry.get("id") or "?"
        subject = entry.get("subject") or ""
        lead_faults = copyprompts.subject_faults(subject, seen=seen)
        if lead_faults:
            faults.append({"lead_id": lead_id, "subject": subject,
                           "faults": lead_faults})
        seen.add(subject.lower().strip())
    return faults


def run_lint(leads_with_copy, packs=None):
    """Stage 5b: run `copylint.check_batch` over the leads.

    `leads_with_copy` is a list of lead dicts in copylint's expected shape.
    `packs` maps lead_id to research pack.
    """
    from . import copylint
    return copylint.check_batch(leads_with_copy, packs=packs)


def classify_leads(extraction_results):
    """Classify leads after extraction into usable, held, errored.

    Returns {usable: [...], held: [...], errored: [...]}.
    """
    usable, held, errored = [], [], []
    results = extraction_results.get("results") or {}
    errors = extraction_results.get("errors") or {}

    for lead_id, result in results.items():
        if result.get("usable", True) and result.get("facts"):
            usable.append({"lead_id": lead_id, **result})
        else:
            held.append({"lead_id": lead_id, **result})

    for lead_id, error in errors.items():
        errored.append({"lead_id": lead_id, **error})

    return {"usable": usable, "held": held, "errored": errored}


def pipeline_report(clean_metrics, extraction_results, subject_faults,
                    lint_report, writing_blocked_reason=None):
    """Assemble the headline numbers for the task's report."""
    classified = classify_leads(extraction_results)
    report = {
        "stage_1_cleaning": clean_metrics,
        "stage_3_extraction": {
            "total": extraction_results.get("total", 0),
            "extracted": extraction_results.get("extracted", 0),
            "errored": extraction_results.get("errored", 0),
            "held": len(classified["held"]),
            "usable": len(classified["usable"]),
        },
        "stage_4_writing": {
            "blocked": True,
            "reason": writing_blocked_reason or (
                "No ANTHROPIC_API_KEY and no Anthropic adapter. "
                "The operator chose two models deliberately; "
                "gpt-oss-120b is not a substitute for the writer."),
        },
        "stage_5_lint": {
            "subject_faults": len(subject_faults),
            "subject_fault_details": subject_faults,
            "copylint": {
                "refused": lint_report.get("refused", False),
                "clean": lint_report.get("clean", 0),
                "leads": lint_report.get("leads", 0),
                "counts": lint_report.get("counts", {}),
            } if lint_report else None,
        },
    }
    return report
