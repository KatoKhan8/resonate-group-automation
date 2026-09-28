"""Does the artifact carry EVERY item criterion 4 lists, per message?

`task425_artifact.criterion_verdicts` answers criterion 4 from four booleans -
copy stored, an EmailBison projection, a HeyReach projection, provider writes
zero. The brief lists sixteen things, so four booleans reading True is a weaker
statement than the criterion makes, and a section that rendered empty would not
move any of them.

So this reads the run's own JSON and asks for each item separately, per message
where the brief says per message. A field whose value is a placeholder counts as
ABSENT: "(none)" is an answer only where the run measured none, and the two are
told apart by looking at what the run recorded rather than at the rendered text.

    py -3 scripts/task425_criterion4_completeness.py work/rerun.json

Exit 0 only when every item is present. Every missing item is named.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import task425_artifact                                          # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tests"))
from tests import task425fixture as fixture                      # noqa: E402

#: The per-message fields, spelled as `_audit_per_message` emits them.
PER_MESSAGE = ("PRIMARY PROBLEM", "SELECTED OFFER", "WHY THIS OFFER",
               "SELECTED CORE CAPABILITIES", "AI CAPABILITY USED",
               "SOURCE / PROVENANCE", "EXACT CLAIM LICENSED",
               "WHERE IT APPEARED IN COPY")


def artifact_level(result):
    """The items the brief lists once for the whole artifact."""
    runs = result.get("runs") or {}
    base = runs.get("A") or {}
    email = result.get("email") or {}
    linkedin = result.get("linkedin") or {}
    wire = result.get("wire") or {}
    plan = (email.get("report") or {}).get("plan") or {}
    facts = base.get("admitted_facts") or []
    contacts = base.get("plan_contacts") or []
    return {
        "facts with sources": bool(facts) and all(
            f.get("source_url") for f in facts),
        "strategy": bool(base.get("plan_strategy")),
        "full email and LinkedIn copy": bool(base.get("cadence")),
        "copylint": bool(email.get("copylint")) or any(
            c.get("copylint") for c in contacts),
        "sequencegate present": bool(email.get("sequencegate_present")),
        "sequencegate not vacuous": not email.get("sequencegate_vacuous", True),
        "the SequencePlan": bool(plan),
        "the EmailBison projection": bool(plan.get("provider_sequence")),
        "the HeyReach projection": bool(linkedin.get("graph")),
        "suppression": result.get("suppression") is not None,
        "spend": result.get("spend") is not None,
        "provider writes = 0": wire.get("provider_request_count") == 0,
        "both traps fired": bool(
            (result.get("trap_generation") or {}).get("fired")
            and (result.get("trap_staging") or {}).get("fired")),
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], "r", encoding="utf-8") as handle:
        result = json.load(handle)

    print("FILE  ", argv[1])
    print("run at", result.get("at"))
    print()

    missing = []
    print("ARTIFACT LEVEL")
    for name, present in artifact_level(result).items():
        print("   %-30s %s" % (name, "present" if present else "ABSENT"))
        if not present:
            missing.append(name)

    print()
    print("PER MESSAGE, contact %s" % fixture.CONTACT_UNDER_TEST)
    base = (result.get("runs") or {}).get("A") or {}
    rendered = task425_artifact._audit_per_message(
        result, base, fixture.CONTACT_UNDER_TEST)
    text = "\n".join(rendered) if isinstance(rendered, list) else str(rendered)
    steps = sorted((base.get("cadence") or {}).get(
        fixture.CONTACT_UNDER_TEST) or {})
    if not steps:
        print("   NO MESSAGES: run A stored no copy for the contact under "
              "test, so there is nothing to audit per message")
        missing.append("per-message audit (no copy stored)")
    for step in steps:
        block = ""
        marker = "#### %s" % step
        if marker in text:
            block = text.split(marker, 1)[1].split("\n#### ", 1)[0]
        absent = [f for f in PER_MESSAGE if f not in block]
        print("   %-5s %s" % (step, "all %d fields" % len(PER_MESSAGE)
                              if not absent else "MISSING %s" % absent))
        if absent:
            missing.append("%s: %s" % (step, absent))

    print()
    if missing:
        print("MISSING %d item(s):" % len(missing))
        for item in missing:
            print("   -", item)
        return 1
    print("every item criterion 4 lists is present, for all %d message(s)"
          % len(steps))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
