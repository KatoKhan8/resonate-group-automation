"""S5: two independent fresh verifications per address, over the staging journal.

USES THE PRODUCTION PATH UNCHANGED. `verification.verify` already encodes
every safety rule batch 1 requires - `required_confirmations: 2`,
`disagreement: hold`, and `sendable` assigned in exactly one place. Nothing
here re-implements verification, and the policy is NOT edited: operator
decision 2026-09-21 is that the stated order "ContactOut, Reoon, Deliverable"
is satisfied by the configured roles, with Reoon keeping the catch-all job it
holds through `accept_all_clears_on`.

RESUMABLE, BECAUSE THIS IS THE EXPENSIVE STAGE. Every address that gets an
answer is appended to the journal before the next is asked, so an interrupt
costs one address and never re-buys a verdict already held. `verify` itself
refuses to re-ask a provider whose answer is already on the contact.

SENDABLE IS NOT READY. This stage produces the verification half only. A lead
is READY when S6 collision and suppression have also cleared it fail-closed,
S7 has rendered copy, the MX decision is known_allowed or unknown_provider,
and the ICP verdict is IN. Those are separate columns in the journal and this
script never sets them.

    py -3 scripts/stage_s5_verify.py                # all of them
    py -3 scripts/stage_s5_verify.py --limit 200    # a slice
    py -3 scripts/stage_s5_verify.py --s3 work/stage/mx-amended-PRODUCTIVE-2026-09-07.jsonl

The third form is the 09-07 backlog. The default input is the 09-21 S3 pass
and no longer agrees with the funnel - see `--s3` in `main`.
"""

import argparse
import concurrent.futures as cf
import csv
import datetime
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import clients, verification                           # noqa: E402
from src.providers import load_env                              # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")
S3 = os.path.join(STAGE, "s3-icp.jsonl")
JOURNAL = os.path.join(STAGE, "s5-verify.jsonl")
SOURCE = os.path.join(ROOT, "work", "Productive",
                      "productive_ICP_safe_to_send (1).csv")

# MX outcomes that permit the email channel. `known_blocked` and `no_mx` were
# already excluded at S4b; `dns_failure` is HELD because we could not ask,
# which is not the same fact as "no mail accepted".
MX_OK = ("known_allowed", "unknown_provider")


def eligible_domains(path=None):
    """IN domains whose email channel S4b left open."""
    out = {}
    with open(path or S3, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if (row.get("verdict") == "in"
                    and row.get("email_channel") is True
                    and row.get("mx") in MX_OK):
                out[row["domain"]] = row
    return out


# A HOLD CAUSED BY A RATE-LIMITED PRIMARY IS NOT A VERDICT.
#
# Measured 2026-09-21: 980 of 1,052 holds read "reoon says valid but the
# primary is missing". ContactOut was answering 429 and billing nothing - the
# addresses were fine, the concurrency was not. Recording those as settled
# would bake a throttling artifact into batch 1 and they would never be
# re-asked, because `done_keys` skips anything already in the journal.
#
# So they are re-askable. The policy itself is untouched: a genuine
# "primary is missing" after a real answer still holds, it just gets asked
# again rather than being final on the first throttled try.
RETRYABLE = ("primary is missing", "primary is unknown",
             "every verifier failed")


def done_keys():
    """Addresses whose verdict is SETTLED. A throttled hold is not settled."""
    out = set()
    if not os.path.exists(JOURNAL):
        return out
    with open(JOURNAL, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            reason = str(row.get("reason") or "")
            if any(flag in reason for flag in RETRYABLE):
                out.discard(row.get("email"))
                continue
            if row.get("email"):
                out.add(row["email"])
    return out


def contacts_for(domains):
    """Every contact in the source file on one of these domains."""
    rows = []
    with open(SOURCE, newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            email = (raw.get("Work Email") or "").strip().lower()
            if "@" not in email:
                continue
            domain = email.rsplit("@", 1)[1]
            if domain in domains:
                rows.append({
                    "key": email,
                    "email": email,
                    "domain": domain,
                    "first_name": (raw.get("First Name") or "").strip(),
                    "title": (raw.get("Job Title") or "").strip(),
                    "company": (raw.get("Company") or "").strip(),
                    "linkedin": (raw.get("Url") or "").strip(),
                })
    return rows


def pair_of(contact):
    """The providers that actually answered, in the order they answered.

    Condition 1 of the batch-1 grant requires the PAIR recorded per lead, not
    just the verdict - "two independent fresh verifications passed (pair
    recorded per lead)". A state of `verified` without the names cannot be
    audited afterwards.
    """
    names = []
    for entry in verification.all_evidence(contact):
        provider = entry.get("provider")
        if provider and provider not in names and entry.get("status") != "error":
            names.append(provider)
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=8,
                        help="concurrency; size against the TIGHTER provider")
    # THE INPUT IS NAMED, BECAUSE THE DEFAULT ONE IS NO LONGER THE FUNNEL.
    #
    # `s3-icp.jsonl` is the 2026-09-21 pass and it carries verdict `out` on
    # 15,642 domains that the 09-23 amendment moved to `in`; its MX columns
    # are `None` on every one of them, so this script's own predicate sees
    # 4,869 eligible domains where the amended pair sees 18,955. The default
    # is UNCHANGED - repointing it is a spend decision, not a refactor - and
    # this flag is how the operator makes it without editing code.
    parser.add_argument("--s3", default=S3,
                        help="the S3/S4b journal to read eligibility from; "
                             "default is s3-icp.jsonl, which is the 09-21 pass")
    parser.add_argument("--report-every", type=int, default=900,
                        help="seconds between progress lines; default 15 min")
    args = parser.parse_args(argv)

    load_env()
    os.makedirs(STAGE, exist_ok=True)
    config = clients.load("productive")
    # THE CLIENT'S POLICY, NOT THE MODULE DEFAULT.
    #
    # This read DEFAULT_POLICY, which was harmless only while the two agreed.
    # On 2026-09-21 the operator removed ContactOut from Productive's
    # VERIFICATION roles - primary deliverable, secondary reoon, reoon keeps
    # the catch-all - and left the defaults alone for every other workspace.
    # `policy_for` is the mechanism built for exactly that, and a runner that
    # ignores it would have kept verifying with a provider the operator
    # removed while the config said otherwise.
    policy = verification.policy_for(config)
    print(f"  policy: primary={policy['primary']} "
          f"secondary={policy['secondary']} catch_all={policy['catch_all']} "
          f"confirmations={policy['required_confirmations']}", flush=True)

    domains = eligible_domains(args.s3)
    print(f"  eligibility from {os.path.relpath(args.s3, ROOT)}", flush=True)
    already = done_keys()
    people = [c for c in contacts_for(domains) if c["email"] not in already]
    print(f"S5  eligible domains {len(domains)}  contacts to verify "
          f"{len(people)}  already done {len(already)}", flush=True)
    if args.limit:
        people = people[:args.limit]

    counts = {}
    started = last = time.time()
    done = 0

    # BOUNDED CONCURRENCY, BECAUSE PROVIDER WAIT IS THE WHOLE COST.
    #
    # Measured 2026-09-21: sequentially this runs at 0.35 contacts/sec - about
    # 2.9s each, nearly all of it waiting on two HTTP calls - which is 7.4
    # HOURS for 9,312 addresses. The work is embarrassingly parallel: every
    # contact is its own dict and `verify` touches nothing shared.
    #
    # K=8, AND CONTACTOUT IS NOT IN THIS CLIENT'S POLICY AT ALL.
    #
    # K=3 was set on 2026-09-21 against ContactOut's 60/min, after eight
    # workers made ~168 calls/min and the primary went missing on 93% of
    # addresses. That reasoning was correct about ContactOut and wrong about
    # this runner: the same operator decision that day removed ContactOut
    # from Productive's VERIFICATION roles, and `policy_for(config)` above
    # resolves to primary=deliverable secondary=reoon catch_all=reoon. The
    # binding limit was sized against a provider this script never calls,
    # and the estate paid 351 minutes for 8,387 addresses for it.
    #
    # WHAT IS DOCUMENTED, AND WHAT IS NOT:
    #
    #   Reoon        4/sec, power mode. PROVIDER-ROUTING-POLICY.md, the
    #                operator's standing order of 2026-09-21. It is the only
    #                rate number in this repository for either verifier, and
    #                it is OPERATOR-STATED rather than vendor-published -
    #                docs/PERF-LATENCY-MODEL-2026-09-18.md classifies Reoon's
    #                published limit as NOT DOCUMENTED.
    #   Deliverable  NOT DOCUMENTED ANYWHERE. Not in `src/providers/
    #                deliverable.py`, which carries the transport contract
    #                read off the vendor's API page and no rate; not in any
    #                docs/ evidence file; explicitly UNKNOWN at
    #                docs/PERF-LATENCY-MODEL-2026-09-18.md:266.
    #
    # An unknown limit is not permission to guess one. It is measured, on the
    # real route, bounded, and classified OBSERVED with its date - the method
    # `ratelimit.LimitClassification.OBSERVED` exists for and
    # docs/PERF-CONCURRENCY-MEASURED-2026-09-18.md established.
    #
    # MEASURED 2026-09-24, three arms of 100 real addresses each, same estate,
    # back to back. Every address bought is in the journal and counted toward
    # the backlog, so the sample is spend rather than waste:
    #
    #     K      addr/s   speedup   pair=2    ERROR   verified
    #     3      0.268      1.0x    100/100     0       49%
    #     8      1.105      4.1x    100/100     0       50%
    #     16     1.759      6.6x    100/100     0       45%
    #
    # Both verifiers answered on 300 of 300 addresses at every K. The 09-21
    # failure signature - a pair of one, "the primary is missing" - did not
    # appear once, which is what distinguishes this from that run.
    #
    # K=8 is the default rather than K=16, on three grounds. Each contact
    # makes about one Reoon call, so K=8 is ~1.1 calls/sec against the stated
    # 4/sec - a quarter of the documented ceiling, and K=16 is 1.76/sec, still
    # inside it, so Reoon is not what decides this. Deliverable is, and its
    # limit is UNKNOWN: K=16 buys 59% over K=8 for twice the pressure on the
    # provider nobody has a number for, and the knee is already visible
    # between the two arms. And the escalation rule this repository already
    # wrote down - "a clean run at K is not permission to run at 2K",
    # scripts/measure_provider_concurrency.py - makes a bounded clean arm
    # evidence for that K and not for the next one. K=16 is measured clean and
    # is available with --workers 16; it is not the standing default.
    lock = threading.Lock()

    def one(contact):
        try:
            decision = verification.verify(contact, policy, live=True,
                                           config=config) or {}
            return contact, decision.get("state") or "unknown", \
                decision.get("reason"), None
        except Exception as exc:                                # noqa: BLE001
            return contact, None, None, exc

    with open(JOURNAL, "a", encoding="utf-8") as journal:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for contact, state, reason, exc in pool.map(one, people):
                if exc is not None:
                    # A provider failure is not a verdict. The address is left
                    # ABSENT from the journal so the next pass re-asks it,
                    # rather than written as `unknown`, which looks settled.
                    with lock:
                        print(f"  ERROR {type(exc).__name__}: "
                              f"{str(exc)[:110]}", flush=True)
                    continue

                pair = pair_of(contact)
                with lock:
                    done += 1
                    counts[state] = counts.get(state, 0) + 1
                    journal.write(json.dumps({
                        "email": contact["email"],
                        "domain": contact["domain"],
                        "state": state,
                        "sendable": bool(contact.get("sendable")),
                        "pair": pair,
                        "confirmations": len(pair),
                        "reason": reason,
                        "at": datetime.datetime.now(
                            datetime.timezone.utc).isoformat(),
                    }) + "\n")
                    journal.flush()

                    if (time.time() - last >= args.report_every
                            or done == len(people)):
                        last = time.time()
                        rate = done / max(1e-9, time.time() - started)
                        verified = counts.get(verification.VERIFIED, 0)
                        print(f"  {done}/{len(people)}  verified {verified}  "
                              f"states {counts}  {rate:.2f}/s  "
                              f"{(time.time()-started)/60:.0f}m", flush=True)

    print(f"\nS5 DONE in {(time.time()-started)/60:.1f}m  states {counts}")
    print("  `verified` is the verification half only. READY additionally "
          "needs S6 collision/suppression, S7 copy, and the ICP verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
