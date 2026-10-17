# qwen-coder/0001 census: fail-closed parser of the one-command artefact.
# Every count is measured from the artefact text; any reconciliation failure
# raises and exits non-zero. Nothing here re-decides a verdict.
import json
import re
import sys

PROVIDER_RULES = ("hold_active_sequence", "hold_recent_touch",
                  "hold_total_sends", "cooling_90_days")


def die(msg):
    print("CENSUS FAULT: %s" % msg)
    sys.exit(1)


def main(artefact, expected_sha, expected_contacts):
    text = open(artefact, encoding="utf-8").read()
    if "SHAPE FAULT" in text:
        die("artefact contains SHAPE FAULT")
    lines = text.splitlines()

    sha = [m.group(1) for m in
           (re.match(r"^sha\s+:\s+([0-9a-f]{40})$", l) for l in lines) if m]
    if len(sha) != 1:
        die("expected exactly one sha line, found %d" % len(sha))
    if sha[0] != expected_sha:
        die("artefact sha %s != HEAD %s" % (sha[0], expected_sha))
    conf = [l for l in lines if l.startswith("instrument  : CONFIRMED")]
    if len(conf) != 1:
        die("instrument line not exactly one CONFIRMED: %r" % conf)

    # ---- SECTION 1: rule blocks
    rules = []  # (name, verdict, counts, provider_read, authorities)
    i = 0
    while i < len(lines):
        m = re.match(r"^  ([a-z0-9_]+)$", lines[i])
        if m and i + 1 < len(lines):
            v = re.match(r"^\s+verdict\s+:\s+(.+?)\s+cells pass=(\d+) "
                         r"excl=(\d+) unk=(\d+) n/a=(\d+) of (\d+)\s*$",
                         lines[i + 1])
            if v:
                name = m.group(1)
                verdict = v.group(1).strip()
                counts = {"pass": int(v.group(2)), "excl": int(v.group(3)),
                          "unk": int(v.group(4)), "na": int(v.group(5)),
                          "total": int(v.group(6))}
                j = i + 2
                prov = False
                auths = []
                while j < len(lines) and lines[j].startswith("    "):
                    if "none declared - provider read" in lines[j]:
                        prov = True
                    am = re.match(r"^    authority: (\S+)\s+(\S+)\s", lines[j])
                    if am:
                        auths.append((am.group(1), am.group(2)))
                    j += 1
                rules.append((name, verdict, counts, prov, auths))
                i = j
                continue
        i += 1

    if len(rules) != 23:
        die("expected 23 rule blocks, parsed %d" % len(rules))
    for name, verdict, c, prov, _ in rules:
        if c["total"] != expected_contacts:
            die("rule %s: total %d != cohort %d" % (name, c["total"],
                                                    expected_contacts))
        if c["pass"] + c["excl"] + c["unk"] + c["na"] != c["total"]:
            die("rule %s: cells do not sum to total" % name)

    names = [r[0] for r in rules]
    if len(set(names)) != len(names):
        die("duplicate rule names parsed")

    # ---- cell census over the whole table
    cells_total = sum(r[2]["total"] for r in rules)
    cells_verdict = sum(r[2]["pass"] + r[2]["excl"] for r in rules)
    cells_na = sum(r[2]["na"] for r in rules)
    prov_rules = [r for r in rules if r[0] in PROVIDER_RULES]
    if sorted(r[0] for r in prov_rules) != sorted(PROVIDER_RULES):
        die("the 4 provider-read rules are not all present: %r"
            % [r[0] for r in prov_rules])
    cells_provider_unk = 0
    for name, verdict, c, prov, auths in prov_rules:
        if not prov:
            die("provider rule %s did not print the provider-read authority "
                "line" % name)
        if c["pass"] or c["excl"]:
            die("DEFECT: provider-read rule %s returned a verdict "
                "(pass=%d excl=%d) on synthetic data" % (name, c["pass"],
                                                         c["excl"]))
        cells_provider_unk += c["unk"]
    other_rules = [r for r in rules if r[0] not in PROVIDER_RULES]
    cells_other_unk = sum(r[2]["unk"] for r in other_rules)
    # every cell parsed is accounted for; blank/malformed is what is left of
    # rules x contacts after subtracting every parsed cell state.
    cells_accounted = cells_verdict + cells_na + cells_provider_unk \
        + cells_other_unk
    cells_blank = 23 * expected_contacts - cells_accounted

    # ---- SECTION 2
    sec2 = [m for m in (re.match(
        r"^  (CLEARED|NOT CLEARED \(EXCLUDED\)|NOT CLEARED \(UNKNOWN\))\s+"
        r"(\S+)\s+(\S+)\s+excluded_by=(\S+) unknown_on=(\d+)/(\d+)\s*$", l)
        for l in lines) if m]
    if len(sec2) != expected_contacts:
        die("SECTION 2: expected %d contact lines, parsed %d"
            % (expected_contacts, len(sec2)))
    for m in sec2:
        if int(m.group(6)) != 23:
            die("SECTION 2: unknown_on denominator %s != 23" % m.group(6))

    # ---- SECTION 3 cross-checks
    def grab(pattern, why):
        found = [re.search(pattern, l) for l in lines]
        found = [f for f in found if f]
        if len(found) != 1:
            die("SECTION 3 %s: %d matches for %r" % (why, len(found),
                                                     pattern))
        return found[0]

    m = grab(r"contacts assessed\s+(\d+)/(\d+)", "contacts")
    if (int(m.group(1)), int(m.group(2))) != (expected_contacts,
                                             expected_contacts):
        die("contacts assessed != %d/%d" % (expected_contacts,
                                            expected_contacts))
    m = grab(r"rules asked\s+(\d+)/(\d+)\s+\(RULES at this SHA: (\d+); "
             r"channel (\w+)\)", "rules")
    if (m.group(1), m.group(2), m.group(3)) != ("23", "23", "23"):
        die("rules asked/RULES != 23/23/23: %r" % m.groups())
    if m.group(4) != "email":
        die("channel != email: %r" % m.group(4))
    m = grab(r"rule verdicts\s+REFUSED (\d+)/23\s+NOT CLEARED (\d+)/23\s+"
             r"UNKNOWN (\d+)/23\s+CLEARED (\d+)/23\s+NOT CONSULTED (\d+)/23",
             "rule verdicts")
    rv = {k: int(m.group(i + 1)) for i, k in enumerate(
        ("refused", "not_cleared", "unknown", "cleared", "not_consulted"))}
    if sum(rv.values()) != 23:
        die("rule verdicts do not sum to 23: %r" % rv)
    rv_recount = {k: 0 for k in rv}
    for _, verdict, _, _, _ in rules:
        key = {"REFUSED": "refused", "NOT CLEARED": "not_cleared",
               "UNKNOWN": "unknown", "CLEARED": "cleared",
               "NOT CONSULTED": "not_consulted"}.get(verdict)
        if key is None:
            die("unrecognised rule verdict %r" % verdict)
        rv_recount[key] = rv_recount.get(key, 0) + 1
    if rv_recount != rv:
        die("SECTION 1 rule verdicts %r disagree with SECTION 3 %r"
            % (rv_recount, rv))
    m = grab(r"authorities POPULATED\s+(\d+)/(\d+)", "authorities")
    auth_pop = (int(m.group(1)), int(m.group(2)))
    m = grab(r"controls OK\s+(\d+)/(\d+)", "controls")
    controls = (int(m.group(1)), int(m.group(2)))
    if controls[0] != controls[1]:
        die("controls not all OK: %r" % (controls,))
    m = grab(r"rules with no evaluable form at this SHA: (\d+)/(\d+); "
             r"provider-read rules: (\d+)/(\d+)", "no-form/provider")
    noform, providern = int(m.group(1)), int(m.group(3))
    if (m.group(2), m.group(4)) != ("23", "23"):
        die("no-form/provider denominators != 23")
    if providern != len(PROVIDER_RULES):
        die("provider-read count %d != %d" % (providern,
                                              len(PROVIDER_RULES)))
    m = grab(r"^\s+exit (\d)\s", "exit")
    exit_line = int(m.group(1))
    m = grab(r"contact verdicts\s+CLEARED (\d+)/(\d+)\s+NOT CLEARED "
             r"\(EXCLUDED\) (\d+)/(\d+)\s+NOT CLEARED \(UNKNOWN\) (\d+)/(\d+)",
             "contact verdicts")
    cv = [int(m.group(i)) for i in (1, 3, 5)]
    if sum(cv) != expected_contacts:
        die("contact verdicts do not sum to cohort: %r" % cv)
    sec2_counts = [0, 0, 0]
    for mm in sec2:
        sec2_counts[("CLEARED", "NOT CLEARED (EXCLUDED)",
                     "NOT CLEARED (UNKNOWN)").index(mm.group(1))] += 1
    if sec2_counts != cv:
        die("SECTION 2 verdict counts %r != SECTION 3 %r"
            % (sec2_counts, cv))

    out = {
        "artefact": artefact,
        "sha_matches_head": True,
        "rule_blocks": len(rules),
        "contacts_section2": len(sec2),
        "table": "23 rules x %d contacts = %d cells"
                 % (expected_contacts, 23 * expected_contacts),
        "cells_real_verdict_pass": sum(r[2]["pass"] for r in rules),
        "cells_real_verdict_excl": sum(r[2]["excl"] for r in rules),
        "cells_real_verdict": cells_verdict,
        "cells_not_applicable": cells_na,
        "cells_provider_read_unknown": cells_provider_unk,
        "cells_other_unknown": cells_other_unk,
        "cells_blank_or_malformed": cells_blank,
        "sum_check": cells_verdict + cells_na + cells_provider_unk
        + cells_other_unk + cells_blank == 23 * expected_contacts,
        "rule_verdicts": rv,
        "contact_verdicts_cleared_excluded_unknown": cv,
        "authorities_populated": list(auth_pop),
        "controls_ok": list(controls),
        "no_form_rules": noform,
        "provider_read_rules": providern,
        "exit_line": exit_line,
        "per_rule": [{"name": n, "verdict": v, **c}
                     for n, v, c, _, _ in rules],
    }
    if cells_blank != 0:
        die("blank/malformed cells: %d" % cells_blank)
    print(json.dumps(out, indent=1))
    print("CENSUS OK: all counts reconcile; nothing was subtracted silently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
