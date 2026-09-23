"""Second-stage LLM tiebreaker over the FLAGGED domains that CAN be judged.

Reads the amended S3 journal, isolates the 5,851 FLAGGED domains whose rows
carry company data (employees, country, industry), and asks a model to
re-decide each one against the client's ICP narrative.  Writes a SEPARATE
journal - never mutates the baseline or the amended file.

THE TWO POPULATIONS INSIDE FLAGGED MUST NOT BE SENT TOGETHER.

    5,851   headcount not judged, geo not confirmed  -> JUDGE THESE
    2,519   provider returned no company for domain  -> UNRESOLVABLE

The 2,519 have no company behind the domain to reason about.  Sending them
costs money to be told what the journal already knows.  They are counted
separately in the report and named "no company data", never as a verdict.

COST.  The model is `llm.from_env()` behind an explicit `--spend` flag.
Without it the script refuses loudly rather than judging nothing silently.
`spendledger` records EXPECTED cost at call time; a report that quotes only
that prints the word ESTIMATED_ONLY rather than a bare dollar figure.

    py -3 scripts/stage_s3_llm_judge.py                 # refuses, no model
    py -3 scripts/stage_s3_llm_judge.py --spend         # calls the model
    py -3 scripts/stage_s3_llm_judge.py --spend --limit 10
"""

import argparse
import collections
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, llm                                  # noqa: E402

STAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "work", "stage")
AMENDED = os.path.join(STAGE, "s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl")
OUTPUT = os.path.join(STAGE, "s3-icp-llm-judge.jsonl")

VALID_VERDICTS = ("in", "out", "flagged")
VALID_CONFIDENCE = ("high", "medium", "low")

NO_COMPANY_REASON = "provider returned no company for this domain"


def rows(path):
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def split_populated(rows_in):
    """Split into (judgeable, no_company_data).

    A row is "no company data" when its reason says the provider returned
    nothing.  Every other FLAGGED row is judgeable: it carries employees,
    country and/or industry that a model can reason about.
    """
    judgeable = []
    no_company = []
    for r in rows_in:
        if r.get("verdict") != "flagged":
            continue
        if r.get("reason") == NO_COMPANY_REASON:
            no_company.append(r)
        else:
            judgeable.append(r)
    return judgeable, no_company


def icp_narrative(icp):
    """Build a plain-language ICP description from the client config.

    The model needs to know WHAT Productive's ideal customer looks like, not
    just the raw config keys.  The narrative is assembled from the same
    fields `judge()` reads, so the model and the rule-based pass reason about
    the same dimensions.
    """
    parts = []
    must = icp.get("must") or ""
    if must:
        parts.append(f"Must: {must}.")

    size_min = icp.get("size_min_employees")
    size_max = icp.get("size_max_employees")
    if size_min and size_max:
        parts.append(f"Company size: {size_min} to {size_max} employees.")
    elif size_min:
        parts.append(f"Company size: at least {size_min} employees.")

    geos = icp.get("geos") or []
    if geos:
        parts.append(f"Target geographies: {', '.join(geos)}.")

    exclude = icp.get("exclude_geos") or []
    if exclude:
        parts.append(f"Excluded geographies: {', '.join(exclude)}.")

    return " ".join(parts)


def build_prompt(row, narrative):
    """One prompt per domain.  The row's own fields are the evidence.

    TASK-272's warning: a reason generated from the verdict rather than from
    the evidence is how "scored above threshold" once appeared on rows
    scoring 0.0.  The prompt must ask the model to reason from the FIELDS
    (employees, country, industry) and produce a reason grounded in them.
    """
    domain = row.get("domain", "")
    employees = row.get("employees")
    country = row.get("country") or ""
    industry = row.get("industry") or ""
    original_reason = row.get("reason") or ""

    return f"""You are a second-stage judge for ICP qualification.  A rule-based pass flagged this domain because it could not decide.  Your job is to look at the evidence and make a call.

ICP NARRATIVE:
{narrative}

DOMAIN: {domain}
EVIDENCE:
- employees (headcount): {employees if employees is not None else "unknown"}
- country: {country if country else "unknown"}
- industry: {industry if industry else "unknown"}
- original flag reason: {original_reason}

Decide: is this domain IN (matches the ICP), OUT (definitely does not), or FLAGGED (still uncertain)?
State your confidence: high, medium, or low.
Give ONE sentence of reason grounded in the evidence fields above - not in your verdict.  A reason that restates the verdict ("scored above threshold") is rejected.

Return JSON only:
{{"verdict": "in"|"out"|"flagged", "confidence": "high"|"medium"|"low", "reason": "one sentence"}}"""


def parse_judge_response(text):
    """Parse and validate the model's response.

    Returns (verdict, confidence, reason) or raises ValueError.
    """
    data = llm.parse(text)
    verdict = data.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"verdict must be one of {VALID_VERDICTS}, "
                         f"not {verdict!r}")
    confidence = data.get("confidence")
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"confidence must be one of {VALID_CONFIDENCE}, "
                         f"not {confidence!r}")
    reason = (data.get("reason") or "").strip()
    if not reason:
        raise ValueError("reason is empty")
    return verdict, confidence, reason


def judge_one(model, row, narrative, rec=None):
    """Ask the model about one domain.  Returns (verdict, confidence, reason).

    On any failure - model error, schema error, parse error - returns the
    ORIGINAL verdict with low confidence and a reason saying the model could
    not decide.  A domain the model does not answer for keeps its original
    verdict rather than defaulting to one.
    """
    prompt = build_prompt(row, narrative)
    try:
        mark = llm.usage_mark(model)
        text = model.complete(prompt)
        llm.record_usage_since(rec, "llm_judge", model, mark)
        verdict, confidence, reason = parse_judge_response(text)
        return verdict, confidence, reason
    except Exception as e:                                  # noqa: BLE001
        return (row.get("verdict", "flagged"), "low",
                f"model could not decide: {type(e).__name__}: "
                f"{str(e)[:120]}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spend", action="store_true",
                        help="opt in to calling the model (costs money)")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after this many domains")
    parser.add_argument("--client", default="productive",
                        help="client config name (default: productive)")
    parser.add_argument("--output", default=OUTPUT,
                        help="output journal path")
    args = parser.parse_args(argv)

    client_config = clients.load(args.client)
    icp = client_config.get("market") or {}
    narrative = icp_narrative(icp)

    base = rows(AMENDED)
    flagged_judgeable, flagged_no_company = split_populated(base)

    print(f"amended journal: {len(base)} rows")
    print(f"  FLAGGED total: "
          f"{sum(1 for r in base if r.get('verdict') == 'flagged')}")
    print(f"  judgeable:     {len(flagged_judgeable)}")
    print(f"  no company data (unresolvable): {len(flagged_no_company)}")

    if args.limit:
        flagged_judgeable = flagged_judgeable[:args.limit]

    # REFUSE LOUDLY RATHER THAN JUDGE NOTHING SILENTLY.
    model = None
    if args.spend:
        model = llm.from_env()
        if isinstance(model, llm.NoModel):
            print("\nREFUSED: no model configured.  Set LLM_API_KEY, "
                  "LLM_BASE_URL and LLM_MODEL in config/.env, or pass a "
                  "model explicitly.  Cannot judge silently with nothing.")
            return 1
        print(f"\nmodel: {model.name} "
              f"({getattr(model, 'model', 'n/a')})")
    else:
        print("\nDRY RUN: --spend not passed.  No model calls.  "
              "Pass --spend to judge.")

    counts = collections.Counter()
    conf_counts = collections.Counter()
    output_rows = []
    # A pseudo-record for usage tracking.
    rec = {"domain": "__llm_judge__", "model_calls": []}

    for i, row in enumerate(flagged_judgeable):
        if model is not None:
            verdict, confidence, reason = judge_one(model, row, narrative,
                                                    rec=rec)
        else:
            verdict = row.get("verdict", "flagged")
            confidence = "low"
            reason = "dry run - no model called"

        counts[verdict] += 1
        conf_counts[confidence] += 1
        output_rows.append({
            "domain": row.get("domain"),
            "verdict": verdict,
            "confidence": confidence,
            "reason": reason,
            "original_verdict": row.get("verdict"),
            "original_reason": row.get("reason"),
            "employees": row.get("employees"),
            "country": row.get("country"),
            "industry": row.get("industry"),
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

        if (i + 1) % 100 == 0 or (i + 1) == len(flagged_judgeable):
            print(f"  {i + 1}/{len(flagged_judgeable)}  "
                  f"in {counts['in']}  out {counts['out']}  "
                  f"flagged {counts['flagged']}")

    # WRITE THE SEPARATE JOURNAL.
    if model is not None:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with io.open(args.output, "w", encoding="utf-8") as fh:
            for r in output_rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nwrote {args.output}")

    # SET DIFF: the amended flagged set vs the judge's flagged set.
    # LOST must be zero: a domain that was flagged and is now gone is a bug.
    amended_flagged = {r["domain"] for r in base
                       if r.get("verdict") == "flagged"}
    judge_flagged = {r["domain"] for r in output_rows
                     if r["verdict"] == "flagged"}
    judge_in = {r["domain"] for r in output_rows if r["verdict"] == "in"}
    judge_out = {r["domain"] for r in output_rows if r["verdict"] == "out"}

    print(f"\n{'verdict':<12}{'count':>10}")
    for v in ("in", "out", "flagged"):
        print(f"{v:<12}{counts[v]:>10,}")
    print(f"{'total':<12}{sum(counts.values()):>10,}")

    print(f"\nconfidence:")
    for c in ("high", "medium", "low"):
        print(f"  {c:<10}{conf_counts[c]:>10,}")

    print(f"\nSET diff:")
    print(f"  amended FLAGGED       {len(amended_flagged):>8,}")
    print(f"  judge FLAGGED         {len(judge_flagged):>8,}")
    print(f"  judge IN              {len(judge_in):>8,}")
    print(f"  judge OUT             {len(judge_out):>8,}")
    kept = amended_flagged & judge_flagged
    lost = amended_flagged - set(r["domain"] for r in output_rows)
    print(f"  kept flagged          {len(kept):>8,}")
    print(f"  LOST (must be zero)   {len(lost):>8,}")
    if lost:
        print("  !! domains disappeared from the judged set:")
        for d in sorted(lost)[:10]:
            print("    ", d)

    print(f"\nno company data (unresolvable, not judged): "
          f"{len(flagged_no_company):,}")

    # COST REPORT.
    if model is not None:
        usage = llm.token_usage([rec])
        by_model = usage.get("by_model", {})
        for model_name, stats in by_model.items():
            print(f"\ncost report ({model_name}):")
            print(f"  calls:              {stats['calls']}")
            total = stats.get("total_tokens")
            if total == llm.UNKNOWN:
                measured = stats.get("measured_total_tokens", 0)
                print(f"  total_tokens:       ESTIMATED_ONLY "
                      f"(measured {measured:,}, "
                      f"{stats.get('calls_missing_tokens', 0)} calls "
                      f"missing token counts)")
            else:
                print(f"  total_tokens:       {total:,}")
            print(f"  ESTIMATED_ONLY: no authoritative counter exists "
                  f"for this model provider, so the token count is an "
                  f"estimate from the adapter's usage reporting")
    else:
        print(f"\ncost report: DRY RUN, no calls made, no cost")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
