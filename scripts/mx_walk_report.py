"""TASK-284: reconcile the MX walk journal against the amended S3 journal.

DNS only. No credits, no provider, no writes.

Prints the identity:
    S3 rows == MX rows + not-yet-walked + out-at-S3

And the per-verdict census from the real MX journal, with the five outcomes
reported separately.

Usage:
    py -3 scripts/mx_walk_report.py
    py -3 scripts/mx_walk_report.py --s3 path/to/s3.jsonl --mx path/to/mx.jsonl
"""

import argparse
import collections
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import mx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
DEFAULT_S3 = os.path.join(STAGE,
                          "s3-icp-amended-PRODUCTIVE-2026-09-07.jsonl")
DEFAULT_MX = os.path.join(STAGE,
                          "mx-amended-PRODUCTIVE-2026-09-07.jsonl")

# The S5 gate's tuple, from scripts/stage_s5_verify.py:120
MX_OK = ("known_allowed", "unknown_provider")


def rows(path):
    if not os.path.exists(path):
        return []
    with io.open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--s3", default=DEFAULT_S3,
                    help="Path to the amended S3 journal")
    ap.add_argument("--mx", default=DEFAULT_MX,
                    help="Path to the MX walk journal")
    args = ap.parse_args(argv)

    s3_rows = rows(args.s3)
    mx_rows = rows(args.mx)

    if not s3_rows:
        print(f"ERROR: S3 journal not found or empty: {args.s3}")
        return 1
    if not mx_rows:
        print(f"ERROR: MX journal not found or empty: {args.mx}")
        return 1

    s3_by_domain = {r["domain"]: r for r in s3_rows}
    mx_by_domain = {r["domain"]: r for r in mx_rows}

    # The identity: S3 rows == MX rows + not-yet-walked + out-at-S3
    out_at_s3 = {d for d, r in s3_by_domain.items()
                 if r.get("verdict") == "out"}
    walked = set(mx_by_domain.keys())
    not_yet_walked = {d for d in s3_by_domain
                      if d not in walked and d not in out_at_s3}

    # Per-verdict census from the MX journal
    verdict_counts = collections.Counter()
    email_channel_counts = collections.Counter()
    null_mx_count = 0
    unknown_provider_domains = []
    dns_failure_domains = []
    no_mx_domains = []
    known_blocked_domains = []
    known_allowed_domains = []

    for domain, row in mx_by_domain.items():
        status = row.get("mx")
        verdict_counts[status] += 1
        email_channel_counts[row.get("email_channel")] += 1

        if status is None:
            null_mx_count += 1
        elif status == mx.UNKNOWN_PROVIDER:
            unknown_provider_domains.append(domain)
        elif status == mx.DNS_FAILURE:
            dns_failure_domains.append(domain)
        elif status == mx.NO_MX:
            no_mx_domains.append(domain)
        elif status == mx.KNOWN_BLOCKED:
            known_blocked_domains.append(domain)
        elif status == mx.KNOWN_ALLOWED:
            known_allowed_domains.append(domain)

    # Print the identity
    print("=" * 70)
    print("MX WALK RECONCILIATION")
    print("=" * 70)
    print(f"\nS3 journal:  {args.s3}")
    if os.path.exists(args.s3):
        print(f"  mtime: {time.ctime(os.path.getmtime(args.s3))}")
    print(f"MX journal:  {args.mx}")
    if os.path.exists(args.mx):
        print(f"  mtime: {time.ctime(os.path.getmtime(args.mx))}")

    print(f"\nS3 rows:        {len(s3_rows):>8,}")
    print(f"MX rows:        {len(mx_rows):>8,}")
    print(f"Out at S3:      {len(out_at_s3):>8,}")
    print(f"Not yet walked: {len(not_yet_walked):>8,}")

    identity_check = len(mx_rows) + len(not_yet_walked) + len(out_at_s3)
    print(f"\nIDENTITY: S3 rows ({len(s3_rows):,}) == "
          f"MX rows ({len(mx_rows):,}) + "
          f"not-yet-walked ({len(not_yet_walked):,}) + "
          f"out-at-S3 ({len(out_at_s3):,})")
    print(f"  = {identity_check:,}")
    if identity_check == len(s3_rows):
        print("  ASSERTION PASSED")
    else:
        print(f"  ASSERTION FAILED: gap of {len(s3_rows) - identity_check:,}")

    # The 24,404 vs 24,241 gap
    print(f"\n24,404 vs 24,241 gap:")
    print(f"  S3 ICP total: 24,404")
    print(f"  S3 amended:   {len(s3_rows):,}")
    print(f"  Out at S3:    {len(out_at_s3):,}")
    gap = 24404 - len(s3_rows)
    print(f"  Unexplained:  {gap:,} (if 0, the gap is fully explained by out-at-S3)")

    # Per-verdict census
    print(f"\n{'=' * 70}")
    print("PER-VERDICT CENSUS (five outcomes)")
    print(f"{'=' * 70}")
    for status in mx.STATUSES:
        count = verdict_counts.get(status, 0)
        print(f"  {status:<22} {count:>8,}")
    other = sum(v for k, v in verdict_counts.items() if k not in mx.STATUSES)
    if other:
        print(f"  {'(other/null)':<22} {other:>8,}")

    # Email channel
    print(f"\nEmail channel:")
    print(f"  open:   {email_channel_counts.get(True, 0):>8,}")
    print(f"  closed: {email_channel_counts.get(False, 0):>8,}")

    # The unknown_provider split
    print(f"\n{'=' * 70}")
    print("unknown_provider SPLIT")
    print(f"{'=' * 70}")
    print(f"  Total unknown_provider: {len(unknown_provider_domains):,}")
    print(f"  (Split requires DNS re-probe: resolved MX we don't recognise")
    print(f"   vs resolver that did not answer. The walk's journal does not")
    print(f"   distinguish these - both are written as 'unknown_provider'.)")

    # dns_failure
    print(f"\n{'=' * 70}")
    print("dns_failure")
    print(f"{'=' * 70}")
    print(f"  Count: {len(dns_failure_domains):,}")
    print(f"  S5 gate refuses: MX_OK = {MX_OK}")
    print(f"  dns_failure in MX_OK: {mx.DNS_FAILURE in MX_OK}")

    # Null mx
    print(f"\n{'=' * 70}")
    print("NULL MX")
    print(f"{'=' * 70}")
    print(f"  Rows with null mx after walk: {null_mx_count:,}")

    # Sample domains per verdict
    print(f"\n{'=' * 70}")
    print("SAMPLE DOMAINS PER VERDICT")
    print(f"{'=' * 70}")
    for label, domains in [("known_blocked", known_blocked_domains),
                           ("unknown_provider", unknown_provider_domains),
                           ("dns_failure", dns_failure_domains),
                           ("no_mx", no_mx_domains),
                           ("known_allowed", known_allowed_domains)]:
        sample = domains[:3]
        print(f"\n  {label} ({len(domains):,} total):")
        for d in sample:
            row = mx_by_domain.get(d, {})
            hosts = row.get("mx_records") or []
            if isinstance(hosts, list):
                print(f"    {d}  MX: {', '.join(hosts[:3]) or 'none'}")
            else:
                print(f"    {d}  MX: {hosts}")

    # S5 eligibility
    s5_eligible = sum(1 for r in mx_by_domain.values()
                      if r.get("verdict") == "in"
                      and r.get("email_channel") is True
                      and r.get("mx") in MX_OK)
    print(f"\n{'=' * 70}")
    print("S5 ELIGIBILITY")
    print(f"{'=' * 70}")
    print(f"  Domains passing S5 gate: {s5_eligible:,}")
    print(f"  Domains refused: {len(mx_by_domain) - s5_eligible:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
