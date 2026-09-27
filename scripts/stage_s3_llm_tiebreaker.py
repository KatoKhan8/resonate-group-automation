"""LLM tiebreaker for the FLAGGED domains the rule-based judge could not decide.

OPERATOR INSTRUCTION, 2026-09-23: a second-stage judge over the FLAGGED
domains with the operator's ICP narrative. Verdict, confidence and a
one-sentence reason per domain. Cost reported.

THE POPULATION. `work/stage/s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl` holds
24,404 domains. The FLAGGED split into two:

    ~5,851   headcount not judged, geo not confirmed  -- THIS SCRIPT JUDGES
    ~2,519   provider returned no company for this domain  -- UNRESOLVABLE

The 2,519 are counted separately and NEVER sent to the model.

THE PATTERN. Copied from `stage_s3_rejudge_amended.py`: read the journal,
decide, write a SEPARATE journal, print a SET diff with a `LOST (must be
zero)` assertion. Does not mutate the amended file.

THE MODEL. `src/llm.py` `NoModel` is the default. `from_env()` requires
explicit opt-in. A run with no model configured REFUSES loudly rather than
judging nothing silently. The `--live` flag is the opt-in to spend.

COST. `spendledger` records EXPECTED cost at call time. A report that quotes
only that prints `ESTIMATED_ONLY` rather than a bare dollar figure.

THE REASON. TASK-272's warning: a reason generated from the verdict rather
than from the evidence is how `"scored above threshold"` once appeared on
rows scoring 0.0. The prompt instructs the model to ground its reason in the
row's own fields (employees, country, industry, reason). The script validates
that the reason is non-empty and does not merely restate the verdict.

    py -3 scripts/stage_s3_llm_tiebreaker.py              # dry run, refuses
    py -3 scripts/stage_s3_llm_tiebreaker.py --live        # calls the model
    py -3 scripts/stage_s3_llm_tiebreaker.py --limit 10    # cap for testing
"""

import argparse
import collections
import datetime
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util                                          # noqa: E402
from src import clients, llm                                   # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "stage_s3_icp", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "stage_s3_icp.py"))
s3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s3)

AMENDED = os.path.join(s3.STAGE, "s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl")
OUTPUT = os.path.join(s3.STAGE, "s3-icp-llm-tiebreaker.jsonl")

NO_COMPANY_REASON = "provider returned no company for this domain"

PROMPT_TEMPLATE = """\
You are judging whether a company fits a client's ideal customer profile (ICP).

## Client ICP narrative

{icp_narrative}

## Company data

Domain: {domain}
Employees: {employees}
Country: {country}
Industry: {industry}
Current status: FLAGGED (the rule-based judge could not decide)
Rule-based reason: {reason}

## Task

Decide whether this company is IN (fits the ICP), OUT (does not fit), or
should remain FLAGGED (evidence is insufficient to decide either way).

Return strict JSON with exactly three fields:
- "verdict": one of "in", "out", "flagged"
- "confidence": one of "high", "medium", "low"
- "reason": ONE sentence explaining your verdict, grounded in the company data
  above (employees, country, industry). Do NOT restate the verdict - explain
  WHY using the specific evidence. A reason like "fits the criteria" is
  rejected. Cite the actual fields.
"""


def rows(path):
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def is_judgeable(r):
    """FLAGGED and NOT the no-company-data population."""
    if r.get("verdict") != "flagged":
        return False
    if r.get("reason") == NO_COMPANY_REASON:
        return False
    return True


def build_prompt(row, icp_narrative):
    return PROMPT_TEMPLATE.format(
        icp_narrative=icp_narrative,
        domain=row.get("domain", ""),
        employees=row.get("employees", "unknown"),
        country=row.get("country", "unknown"),
        industry=row.get("industry", "unknown"),
        reason=row.get("reason", ""),
    )


def parse_response(text):
    """Strict JSON: verdict, confidence, reason. Returns (data, error)."""
    body = (text or "").strip()
    fence = None
    import re
    fence = re.search(r"```(?:json)?\s*(.+?)```", body, re.S)
    if fence:
        body = fence.group(1).strip()
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None, "invalid JSON"
    if not isinstance(data, dict):
        return None, "response is not an object"
    verdict = data.get("verdict")
    if verdict not in ("in", "out", "flagged"):
        return None, f"verdict must be in/out/flagged, got {verdict!r}"
    confidence = data.get("confidence")
    if confidence not in ("high", "medium", "low"):
        return None, f"confidence must be high/medium/low, got {confidence!r}"
    reason = data.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return None, "reason must be a non-empty string"
    return data, None


def validate_reason(data, row):
    """TASK-272: the reason must be grounded in the row's fields, not the
    verdict. A reason that merely restates the verdict is rejected."""
    reason = (data.get("reason") or "").lower().strip()
    verdict = data.get("verdict", "")
    tautologies = {
        "in": ["fits the criteria", "meets the criteria", "is a good fit",
                "matches the icp", "is in market"],
        "out": ["does not fit", "is not a fit", "does not match",
                "is not in market"],
        "flagged": ["insufficient evidence", "cannot determine",
                     "not enough information"],
    }
    for taut in tautologies.get(verdict, []):
        if reason == taut:
            return False, f"reason is a tautology: {reason!r}"
    return True, None


def icp_narrative(icp):
    """Build a human-readable ICP summary for the prompt."""
    parts = []
    if icp.get("must"):
        parts.append(f"Must-have: {icp['must']}")
    lo = icp.get("size_min_employees")
    hi = icp.get("size_max_employees")
    if lo or hi:
        parts.append(f"Size: {lo or 0}-{hi or 'unlimited'} employees")
    geos = icp.get("geos") or []
    if geos:
        parts.append(f"Target geos: {', '.join(geos)}")
    exclude = icp.get("exclude_geos") or []
    if exclude:
        parts.append(f"Excluded geos: {', '.join(exclude)}")
    return "\n".join(parts) if parts else "No ICP narrative configured."


def decided():
    """{domain: row} already in the tiebreaker journal. The checkpoint."""
    out = {}
    if not os.path.exists(OUTPUT):
        return out
    with open(OUTPUT, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("domain"):
                out[row["domain"]] = row
    return out


def cost_report(model, n_calls):
    """Return a cost report dict. Prints ESTIMATED_ONLY when only expected
    cost is available (which is always the case before settlement)."""
    calls = getattr(model, "calls", None)
    if not isinstance(calls, list) or not calls:
        return {"calls": 0, "total_tokens": llm.UNKNOWN,
                "status": "NO_CALLS_MADE",
                "note": "no model calls were made"}

    total_tokens = 0
    has_tokens = True
    for c in calls:
        t = c.get("total_tokens")
        if t is None:
            has_tokens = False
        else:
            total_tokens += t

    report = {
        "calls": len(calls),
        "total_tokens": total_tokens if has_tokens else llm.UNKNOWN,
        "status": "ESTIMATED_ONLY",
        "note": ("cost is estimated from token counts and model pricing; "
                 "actual charge may differ"),
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true",
                        help="actually call the model (costs money)")
    parser.add_argument("--limit", type=int, default=None,
                        help="judge at most this many domains")
    args = parser.parse_args(argv)

    if not os.path.exists(AMENDED):
        print(f"ERROR: amended journal not found at {AMENDED}")
        return 1

    all_rows = rows(AMENDED)
    print(f"amended journal: {len(all_rows)} rows")

    flagged = [r for r in all_rows if r.get("verdict") == "flagged"]
    no_company = [r for r in flagged if r.get("reason") == NO_COMPANY_REASON]
    judgeable = [r for r in flagged if is_judgeable(r)]

    print(f"flagged total:      {len(flagged):>8,}")
    print(f"no company data:    {len(no_company):>8,}  (excluded, unresolvable)")
    print(f"judgeable:          {len(judgeable):>8,}")

    if args.limit:
        judgeable = judgeable[:args.limit]
        print(f"limited to:           {len(judgeable):>8,}")

    already = decided()
    todo = [r for r in judgeable if r["domain"] not in already]
    print(f"already judged:       {len(already):>8,}")
    print(f"todo:                 {len(todo):>8,}")

    if not todo:
        print("nothing to do")
        _print_set_diff(all_rows, already)
        return 0

    if not args.live:
        print("\nDRY RUN: no model will be called. Pass --live to spend.")
        print(f"Would judge {len(todo)} domains.")
        return 0

    model = llm.from_env()
    if isinstance(model, llm.NoModel):
        print("\nREFUSING: no model configured. Set LLM_API_KEY, LLM_BASE_URL "
              "and LLM_MODEL in config/.env, then pass --live.")
        return 1

    client_config = clients.load("productive")
    icp = client_config.get("market") or {}
    narrative = icp_narrative(icp)

    counts = {"in": 0, "out": 0, "flagged": 0}
    errors = 0
    started = time.time()

    os.makedirs(s3.STAGE, exist_ok=True)
    with open(OUTPUT, "a", encoding="utf-8") as journal:
        for i, row in enumerate(todo):
            domain = row["domain"]
            prompt = build_prompt(row, narrative)
            try:
                mark = llm.usage_mark(model)
                text = model.complete(prompt, temperature=0)
                llm.record_usage_since(
                    {"model_calls": []}, "tiebreaker", model, mark)
                data, err = parse_response(text)
                if err:
                    print(f"  {domain}: parse error: {err} - keeping original")
                    errors += 1
                    continue
                valid, verr = validate_reason(data, row)
                if not valid:
                    print(f"  {domain}: reason rejected: {verr} - keeping original")
                    errors += 1
                    continue
                counts[data["verdict"]] += 1
                journal.write(json.dumps({
                    "domain": domain,
                    "verdict": data["verdict"],
                    "confidence": data["confidence"],
                    "reason": data["reason"],
                    "original_reason": row.get("reason"),
                    "employees": row.get("employees"),
                    "country": row.get("country"),
                    "industry": row.get("industry"),
                    "at": datetime.datetime.now(
                        datetime.timezone.utc).isoformat(),
                }) + "\n")
                journal.flush()
            except llm.NoModelConfigured:
                print("\nREFUSING: model became unconfigured mid-run.")
                return 1
            except llm.ModelUnavailable as e:
                print(f"  {domain}: model unavailable: {str(e)[:120]} "
                      f"- keeping original verdict")
                errors += 1
            except llm.ModelError as e:
                print(f"  {domain}: model error: {str(e)[:120]} "
                      f"- keeping original verdict")
                errors += 1

            if (i + 1) % 100 == 0 or (i + 1) >= len(todo):
                print(f"  {i+1}/{len(todo)}  "
                      f"in {counts['in']} out {counts['out']} "
                      f"flagged {counts['flagged']} errors {errors}")

    elapsed = time.time() - started
    print(f"\nDONE in {elapsed:.0f}s")
    print(f"  in {counts['in']}  out {counts['out']}  "
          f"flagged {counts['flagged']}  errors {errors}")

    report = cost_report(model, len(todo))
    print(f"\nCOST: {report['status']}")
    print(f"  calls: {report['calls']}")
    if report["total_tokens"] != llm.UNKNOWN:
        print(f"  total tokens: {report['total_tokens']:,}")
    else:
        print(f"  total tokens: UNKNOWN (some calls did not report usage)")
    print(f"  note: {report['note']}")

    all_decided = decided()
    _print_set_diff(all_rows, all_decided, no_company_count=len(no_company))
    return 0


def _print_set_diff(all_rows, tiebreaker_decided, no_company_count=0):
    """SET diff: the tiebreaker's IN set vs the amended journal's FLAGGED set
    that were judged. LOST must be zero."""
    flagged_domains = {r["domain"] for r in all_rows
                       if r.get("verdict") == "flagged"
                       and r.get("reason") != NO_COMPANY_REASON}
    judged_domains = {d for d in tiebreaker_decided}
    tiebreaker_in = {d for d, r in tiebreaker_decided.items()
                     if r.get("verdict") == "in"}

    print(f"\nSET diff on tiebreaker results:")
    print(f"  judgeable FLAGGED    {len(flagged_domains):>8,}")
    print(f"  no company data      {no_company_count:>8,}  (excluded)")
    print(f"  judged by tiebreaker {len(judged_domains):>8,}")
    print(f"  tiebreaker IN        {len(tiebreaker_in):>8,}")
    unjudged = flagged_domains - judged_domains
    print(f"  unjudged (kept FLAGGED) {len(unjudged):>8,}")
    lost = judged_domains - flagged_domains
    print(f"  LOST (must be zero)  {len(lost):>8,}")
    if lost:
        print("  !! tiebreaker judged domains that were not FLAGGED - bug:")
        for d in sorted(lost)[:10]:
            print("    ", d)


if __name__ == "__main__":
    raise SystemExit(main())
