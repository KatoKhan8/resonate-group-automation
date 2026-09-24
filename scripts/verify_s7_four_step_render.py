#!/usr/bin/env python3
"""Does the S7 journal survive the NEXT stage's question, for all four steps?

    py -3 scripts/verify_s7_four_step_render.py
    py -3 scripts/verify_s7_four_step_render.py --new work/stage/s7-copy.jsonl \\
                                                --old work/stage/s7-copy.jsonl.BAK

READS ONLY. It opens two journals, builds records in memory and calls the real
gates. It writes nothing, touches no provider and loads no credential.

## WHY A SEPARATE SCRIPT, WHEN S7 ALREADY PRINTS A COUNT

Because S7's count answers S7's question. "814 rendered" means every merge
field resolved - it does not mean the words pass `lint.check`, it does not
mean `bisonfactory` will build a sequence out of them, and it does not mean
the provider payload carries a non-empty value for every variable the
template reads. Each of those is a LATER gate with its own opinion, and every
wrong headline number in this project's history came from a stage that had
not asked the next stage's question. So this asks all four, in order, and
reports the number that survives all of them.

    stage 1  the journal      every variable the four-step build reads is
                              present, non-empty, not the string 'None', and
                              carries no unrendered placeholder
    stage 2  the held set     BY EMAIL and in both directions against the
                              previous journal. A count is not a set: "113
                              held" and "113 held" compare equal while a
                              different 113 are held
    stage 3  lint.check       the real approval gate, on the real record
                              shape. A row that renders and fails lint is
                              refused at `approve.why_not` and never ships,
                              so it does not belong in the headline
    stage 4  bisonfactory     _sequence_steps -> _approved_copy ->
                              _variables_for -> _stale_clearances, which is
                              the actual `custom_variables` payload

## WHAT IT DELIBERATELY DOES NOT PROVE

The approval gate's OTHER conditions - verification pair, sendability,
suppression, collision, fatigue - are not exercised. They need `work/` state
this script does not read. A row counted good here is good ON ITS COPY, and
`scripts/batch1_build.py` is still what decides whether it is approvable.

Nothing here is evidence that anything reached EmailBison. Only a provider
readback is.
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import approval, bisonfactory, clients, identity, lint  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE = os.path.join(ROOT, "work", "stage")

#: The journal names the four-step build reads, keyed BY STEP KEY. `body_3`
#: is the retired `breakup` and is deliberately absent: it is still rendered
#: and is no longer sent.
REFERENCED = ("subject_1", "body_1", "body_2", "body_4", "body_5",
              "template_4", "template_5")

#: The provider's variable names, keyed BY POSITION. em4 is the third step
#: and arrives as `body_3`; em5 is the fourth and arrives as `body_4`.
AT_THE_PROVIDER = ("subject_1", "body_1", "body_2", "body_3", "body_4")

#: Values that are "empty" to a human and not to `if value`. The morning
#: handoff warned about the literal `'None'`; 2026-09-24 measured the live
#: variables as EMPTY instead. Both are checked, because the blank gate
#: refuses both and checking only the one that bit last time is how the other
#: one gets through.
BLANKISH = {"", "none", "null", "nan", "n/a", "-"}

#: The lint codes that are about the COPY. A verification or suppression code
#: is a fact about the record, not about the words, and this script does not
#: hold the state to judge those.
COPY_CODES = ("body_too_short", "body_too_long", "subject_too_long",
              "em_dash", "attachment", "placeholder", "banned_phrase",
              "greets_the_wrong_person", "hard_wrapped", "no_question")


def load(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def rendered_by_email(rows):
    return {r["email"].lower(): r for r in rows if r.get("state") == "rendered"}


def cadence_steps():
    """`CADENCE_STEPS` out of the builder, so the two cannot drift.

    Loaded by path: `scripts/` is not a package.
    """
    import importlib.util

    path = os.path.join(ROOT, "scripts", "batch1_build.py")
    spec = importlib.util.spec_from_file_location("batch1_build_for_verify",
                                                  path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CADENCE_STEPS


def build_record(email, variables, existing):
    """One record per DOMAIN, with this contact's four steps on it.

    Grouped by domain because `scripts/batch1_build.py` groups by domain and
    `lint.check` reads the record, not the row - a second contact at the same
    account is a different question from the first.
    """
    domain = email.split("@")[-1]
    rec = existing.get(domain)
    if rec is None:
        rec = {"id": domain.replace(".", "-"), "client": "productive",
               "domain": domain, "state": "verified",
               "company_facts": {"name": "Account", "domain": domain},
               "contacts": [], "cadence": {}, "stages": {}, "events": [],
               "log": [], "excluded": []}
        existing[domain] = rec
    # The greeting name is read back out of the body the same way `lint`
    # reads it, so `greets_the_wrong_person` is asked a real question rather
    # than one this script made agree with itself.
    contact = {"name": variables["body_1"].split(",")[0].strip(),
               "email": email, "title": variables.get("title"),
               "persona": variables.get("persona"),
               "angle": variables.get("angle"), "verdict": "valid",
               "sendable": True, "primary": not rec["contacts"]}
    contact["key"] = identity.contact_key(
        contact, existing=[c.get("key") for c in rec["contacts"]])
    rec["contacts"].append(contact)
    rec["cadence"][contact["key"]] = {
        "em1": {"channel": "email", "template": "persona_pain",
                "generated": True, "subject": variables["subject_1"],
                "body": variables["body_1"]},
        "em2": {"channel": "email", "template": "comparable_proof",
                "generated": True, "subject": variables["subject_1"],
                "body": variables["body_2"]},
        "em4": {"channel": "email", "template": variables["template_4"],
                "generated": True, "subject": variables["subject_1"],
                "body": variables["body_4"]},
        "em5": {"channel": "email", "template": variables["template_5"],
                "generated": True, "subject": variables["subject_1"],
                "body": variables["body_5"]},
    }
    return rec, contact["key"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--new", default=os.path.join(STAGE, "s7-copy.jsonl"))
    parser.add_argument("--old", help="the previous journal, for the held-set "
                                      "diff. Skipped when absent.")
    parser.add_argument("--client", default="productive")
    parser.add_argument("--examples", type=int, default=10)
    args = parser.parse_args(argv)

    new_rows = load(args.new)
    new = rendered_by_email(new_rows)
    print(f"JOURNAL {os.path.basename(args.new)}")
    print(f"  {len(new_rows)} rows, {len(new)} rendered, "
          f"{len(new_rows) - len(new)} held")

    bad = collections.Counter()
    example = {}

    def fault(why, email):
        bad[why] += 1
        example.setdefault(why, email)

    print("\nSTAGE 1  every referenced variable, on every rendered row")
    for email, row in new.items():
        values = row["variables"]
        for name in REFERENCED:
            if name not in values:
                fault(f"{name} ABSENT", email)
            elif values[name] is None:
                fault(f"{name} is None, the object", email)
            elif str(values[name]).strip().lower() in BLANKISH:
                fault(f"{name} is blank or the string 'None'", email)
            elif "{" in str(values[name]) or "}" in str(values[name]):
                fault(f"{name} carries an unrendered placeholder", email)
    if bad:
        for why, count in bad.most_common():
            print(f"  FAIL {why:<52} {count:>5}   e.g. {example[why]}")
    else:
        print(f"  PASS  {len(new)} rows x {len(REFERENCED)} variables = "
              f"{len(new) * len(REFERENCED)} values, none blank, none 'None', "
              f"none unrendered")

    print("\nSTAGE 2  the held set, BY EMAIL, both directions")
    if not args.old or not os.path.exists(args.old or ""):
        print("  SKIPPED - no previous journal given. A first run has nothing "
              "to diff against, and that is not the same as no change")
        regressed = []
    else:
        old = rendered_by_email(load(args.old))
        regressed = sorted(set(old) - set(new))
        gained = sorted(set(new) - set(old))
        moved = [e for e in new if e in old and any(
            new[e]["variables"].get(k) != old[e]["variables"].get(k)
            for k in ("subject_1", "body_1", "body_2", "body_3"))]
        print(f"  rendered before, held now      {len(regressed):>5}")
        for email in regressed[:args.examples]:
            print(f"      {email}")
        print(f"  held before, rendered now      {len(gained):>5}")
        for email in gained[:args.examples]:
            print(f"      {email}")
        print(f"  EXISTING copy moved            {len(moved):>5}   "
              f"(subject_1, body_1..body_3 - live words, and a change here "
              f"is a change to what a prospect is already receiving)")
        for email in moved[:args.examples]:
            print(f"      {email}")

    print("\nSTAGE 3  lint.check, the real approval gate, all four steps")
    config = clients.load(args.client)
    lint.forget_policies()
    records, keys = {}, []
    for email, row in new.items():
        rec, key = build_record(email, row["variables"], records)
        keys.append((rec, key, email))
    lintbad, lintex = collections.Counter(), {}
    refused = set()
    for rec, key, email in keys:
        for step_key, step in rec["cadence"][key].items():
            for code in lint.check(rec, key, step):
                if code in COPY_CODES:
                    lintbad[f"{step_key} {code}"] += 1
                    lintex.setdefault(f"{step_key} {code}", email)
                    refused.add(email)
    print(f"  {len(keys) * 4} steps checked across {len(records)} records")
    if lintbad:
        for why, count in lintbad.most_common():
            print(f"  FAIL {why:<42} {count:>5}   e.g. {lintex[why]}")
        print(f"  {len(refused)} lead(s) carry at least one step lint refuses. "
              f"`approve.why_not` returns 'fails lint' for these and they "
              f"never reach a provider")
    else:
        print("  PASS  no copy-quality failure on any step")

    print("\nSTAGE 4  the custom_variables payload bisonfactory would build")
    sequence = bisonfactory._sequence_steps(config.get("email_sequence"),
                                            cadence_steps())
    print("  sequence  " + " | ".join(
        f"{s['step_key']}@{s['order']} thread_reply={s['thread_reply']} "
        f"subject={s['email_subject']} wait={s['wait_in_days']}"
        for s in sequence))
    referenced = set()
    for step in sequence:
        for field in (step["email_subject"], step["email_body"]):
            referenced.update(m.lower()
                              for m in re.findall(r"\{([A-Z_0-9]+)\}", field))
    missing_names = referenced - set(AT_THE_PROVIDER)
    if missing_names:
        print(f"  NOTE the sequence references {sorted(missing_names)}, which "
              f"this script does not know about. Check them by hand")
    paybad, payex, built = collections.Counter(), {}, 0
    for rec, key, email in keys:
        for step in rec["cadence"][key].values():
            step["approval"] = {"by": "operator",
                                "at": "2026-09-24T00:00:00Z",
                                "fingerprint": approval.fingerprint(step)}
        copy, missing = bisonfactory._approved_copy(
            rec, key, sequence, rec["id"], cadence_steps=cadence_steps(),
            campaign={"client": args.client}, config=config)
        if missing:
            why = "no approved copy for " + ",".join(missing)
            paybad[why] += 1
            payex.setdefault(why, email)
            continue
        lead = {"record_id": rec["id"], "contact_key": key, "email": email,
                "copy": copy}
        values = {v["name"]: v["value"] for v in bisonfactory._variables_for(
            lead, {"client": args.client}, sequence=sequence)}
        cleared = {v["name"]: v["value"]
                   for v in bisonfactory._stale_clearances(sequence)}
        built += 1
        for name in referenced:
            if name not in values:
                paybad[f"{name} absent from custom_variables"] += 1
                payex.setdefault(f"{name} absent from custom_variables", email)
            elif str(values[name]).strip().lower() in BLANKISH:
                paybad[f"{name} blank or 'None' at the provider"] += 1
                payex.setdefault(f"{name} blank or 'None' at the provider", email)
            elif "{" in str(values[name]):
                paybad[f"{name} still unrendered at the provider"] += 1
                payex.setdefault(f"{name} still unrendered at the provider", email)
            elif name in cleared and cleared[name] != values[name]:
                paybad[f"{name} is written and cleared in the same PATCH"] += 1
                payex.setdefault(f"{name} is written and cleared in the same PATCH",
                                 email)
        # A threaded follow-up must carry NO subject of its own.
        for position in range(2, len(sequence) + 1):
            if str(values.get(f"subject_{position}", "")).strip():
                paybad[f"subject_{position} is non-empty on a thread reply"] += 1
                payex.setdefault(f"subject_{position} is non-empty on a thread reply",
                                 email)
    print(f"  {built} leads built")
    if paybad:
        for why, count in paybad.most_common():
            print(f"  FAIL {why:<52} {count:>5}   e.g. {payex[why]}")
    else:
        print(f"  PASS  every lead carries {sorted(referenced)} non-empty, "
              f"and no follow-up subject leaks")

    survivors = len(new) - len(refused)
    print("\nTHE NUMBER THAT SURVIVED EVERY STAGE")
    print(f"  {len(new_rows):>5} rows in the journal")
    print(f"  {len(new):>5} rendered by S7")
    print(f"  {survivors:>5} also pass lint, so also approvable on their copy")
    print(f"  {built:>5} build a complete four-step provider payload")
    print("\n  Not one of these is a send. Only a provider readback is.")
    clean = not bad and not paybad and not regressed
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
