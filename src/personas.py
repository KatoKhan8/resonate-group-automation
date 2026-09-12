#!/usr/bin/env python3
"""Personas, contact selection, and the domains lane export. BUILD-SPEC phase 6.

The three lanes are not the same shape and are not collapsed here:

  domains  a persona set is built from the client config, capped per domain,
           and every kept contact carries a persona and an angle. This is the
           lane section 4 is written for, and the lane where caps are money:
           2 champions plus 1 buyer over 500 domains is 1,500 search credits,
           against 5,000 to 6,000 with no caps.

  revive   the contacts come from the thread. The person who ran the trial is
           kept whether or not they match a persona title, because the record's
           own history is better evidence than a title list. No fan-out.

  cold     the signal names the person. That person is kept. No fan-out.

Everyone not kept stays in `excluded` with a reason, so a human can see what was
thrown away (section 9, trap 1).

  python -m src.personas                 what would be selected
  python -m src.personas --apply         write the selection to the queue
  python -m src.personas --export        write out/domains/<domain>/
"""
import argparse
import csv
import json
import os
import re

from . import clients, events, identity, store

# How strongly a title matches a persona. Higher wins a cap contest.
EXACT, CONTAINS, WORD = 3, 2, 1


def norm_title(title):
    return " ".join((title or "").lower().replace("/", " ").split())


def title_score(title, wanted):
    """Deterministic: exact match beats containment beats a shared word."""
    have, want = norm_title(title), norm_title(wanted)
    if not have or not want:
        return 0
    if have == want:
        return EXACT
    if want in have:
        return CONTAINS
    want_words = [w for w in want.split() if len(w) > 3]
    if want_words and all(w in have for w in want_words):
        return WORD
    return 0


def classify(contact, config):
    """(persona, score) for the best persona this title matches, or (None, 0)."""
    best, best_score = None, 0
    for persona in clients.personas(config):
        for wanted in clients.titles_for(config, persona):
            score = title_score(contact.get("title"), wanted)
            if score > best_score:
                best, best_score = persona, score
    return best, best_score


def family_titles(plan, config):
    """The routing strategy's persona -> titles map, read live.

    The plan stored on the record is a snapshot: `qualify._inputs_fingerprint`
    digests company facts, domain, hook and research, so a title list
    corrected in code never reaches a record whose facts have not moved. The
    strategy *decision* is the durable part and is read from the plan; how a
    title is spelled is code, and is read from the module.
    """
    from . import routing

    name = (plan or {}).get("strategy")
    live = routing.settings(config)["strategies"].get(name)
    return (live or {}).get("personas") or (plan or {}).get("personas") or {}


def family_of(contact, priority, families):
    """Which of the strategy's personas this title belongs to, and its rank.

    Returns (name, rank). Unmatched is (None, len(priority)) - last, never
    first: a title nobody recognises is not evidence of seniority. Ties go to
    the earlier persona in the priority.
    """
    best_name, best_rank, best_score = None, len(priority), 0
    for rank, family in enumerate(priority):
        for wanted in families.get(family) or []:
            score = title_score(contact.get("title"), wanted)
            if score > best_score:
                best_name, best_rank, best_score = family, rank, score
    return best_name, best_rank


def family_rank(contact, priority, families):
    return family_of(contact, priority, families)[1]


def rank_key(entry):
    """Ordering: the strategy's persona priority, then title match, then a
    verified address, then id.

    Priority comes first because it is a stated go-to-market decision and
    `title_score` is not - the score measures how a title is *spelled* against
    the client's list. An exactly spelled "Chief Executive Officer" outscored
    a "President & COO" that merely contained "COO", so the cap kept the CEO
    at a company whose own plan says operations owns the problem before
    founders do.

    Below it, `email` decided a tie, which made the winner of a cap contest
    depend on which person enrichment had reached an address for first: the
    same record selected the COO before addresses arrived and the CEO after.

    The term is inert with no plan - every entry ranks 0 and the order is
    exactly what it was.
    """
    contact, score = entry["contact"], entry["score"]
    return (entry.get("family_rank", 0), -score,
            0 if contact.get("sendable") else 1,
            0 if contact.get("email") else 1, contact.get("key") or "")


def default_angle(config, persona, family=None):
    """The angle this person gets, or None when nothing fits.

    An angle whose key matches the routing family the title belongs to wins:
    an operations lead is written to about operations, a founder about
    founders. The match is by name and the names come from the client's own
    config and the routing strategy, so nothing here knows what any particular
    client sells.

    Falling back to the single angle is kept for a persona that has exactly
    one. What is deliberately *not* done is picking the first of several: a
    finance lead inheriting founder copy because the persona happened to
    define only that angle is the mismatch this exists to stop. No angle
    leaves `angle` None, `lint` raises `domains_contact_no_angle`, and
    `eligibility` blocks on lint - so the person is held rather than written
    to with the wrong words.
    """
    angles = list(clients.angles_for(config, persona))
    if family and family in angles:
        return family
    return angles[0] if len(angles) == 1 else None


def set_aside(contact, why):
    """An excluded contact, kept whole.

    This used to store `{name, title, why}` and drop everything else - the
    email, the LinkedIn URL, the verification evidence. All of it was bought:
    `decision-makers` costs ten credits for the set and each verification
    costs one, so a persona rule excluding somebody threw away paid data and
    made the decision irreversible.

    That is not hypothetical. Two people at this pilot were excluded because
    the client's config listed "COO" and not "Chief Operating Officer";
    correcting the config could not restore them, because what came back was a
    name and a title with no address. Re-including one made
    `usable_contacts` false, and enrichment bought `decision-makers` again for
    the same company - ten credits to rediscover people already on the record.

    An exclusion is a decision about a person, not a reason to forget them.
    """
    return dict(contact, why=why)


# The one exclusion reason that a corrected persona list can undo. A cap
# exclusion is a different decision and the cap has not moved.
NOT_A_PERSONA = "not a persona for this client"


def readmit(rec, config):
    """Return contacts whose exclusion reason has stopped being true.

    `set_aside` keeps an excluded contact WHOLE - address, profile,
    verification evidence, all of it paid for - precisely so that a corrected
    persona list can restore them. Its own docstring gives the case: two
    people were excluded because the client's config said "COO" and not
    "Chief Operating Officer", and "correcting the config could not restore
    them".

    It still could not. `select_domains` reads `rec["contacts"]`, and a
    contact set aside is no longer in it, so nothing this module does looks at
    an exclusion again. Measured on the Productive estate: 26 already-paid
    contacts sat in `excluded` with `persona: None` under this reason while
    `classify` places every one of them - including the estate's only
    resource-management contact, a Design Studio Manager whose title the
    client's config gained on 2026-09-09.

    Only in the safe direction. Nothing is excluded here, a contact already on
    the record is not duplicated, and an entry set aside for any other reason
    is left exactly where it is.
    """
    excluded = rec.get("excluded") or []
    if not excluded:
        return []
    held = [(str(c.get("name") or "").strip().lower(),
             norm_title(c.get("title"))) for c in rec.get("contacts") or []]
    returned, still_out = [], []
    for entry in excluded:
        who = (str(entry.get("name") or "").strip().lower(),
               norm_title(entry.get("title")))
        if (entry.get("why") == NOT_A_PERSONA
                and classify(entry, config)[0]
                and who not in held):
            held.append(who)
            returned.append({k: v for k, v in entry.items() if k != "why"})
        else:
            still_out.append(entry)
    if returned:
        rec["excluded"] = still_out
        rec.setdefault("contacts", []).extend(returned)
        store.log(rec, "personas",
                  f"{len(returned)} contact(s) set aside as "
                  f"'{NOT_A_PERSONA}' now match one: returned to the record "
                  "rather than re-bought")
    return returned


def select_domains(rec, config):
    """The capped persona set for one domain."""
    keep, excluded = [], []
    by_persona = {}
    plan = (rec.get("qualification") or {}).get("persona_plan") or {}
    priority = list(plan.get("persona_priority") or [])
    families = family_titles(plan, config) if priority else {}

    for contact in rec.get("contacts") or []:
        persona, score = classify(contact, config)
        if not persona:
            excluded.append(set_aside(contact, NOT_A_PERSONA))
            continue
        by_persona.setdefault(persona, []).append(
            {"contact": contact, "score": score,
             "family": (family_of(contact, priority, families)[0]
                        if priority else None),
             "family_rank": (family_rank(contact, priority, families)
                             if priority else 0)})

    for persona, entries in by_persona.items():
        cap = clients.cap_for(config, persona)
        entries.sort(key=rank_key)
        for i, entry in enumerate(entries):
            contact = entry["contact"]
            if i < cap:
                contact["persona"] = persona
                if not contact.get("angle"):
                    contact["angle"] = default_angle(
                        config, persona, entry.get("family"))
                keep.append(contact)
            else:
                excluded.append(set_aside(
                    contact, f"over the cap of {cap} for {persona}"))
    return keep, excluded


def select_thread(rec, config, why):
    """revive and cold: keep who the record already knows about."""
    keep, excluded = [], []
    for contact in rec.get("contacts") or []:
        if contact.get("email") or contact.get("linkedin"):
            persona, _ = classify(contact, config)
            contact["persona"] = contact.get("persona") or persona
            keep.append(contact)
        else:
            excluded.append(set_aside(contact, why))
    return keep, excluded


# Country codes as they appear in provider office strings ("Zagreb HR"), for the
# geos a client is likely to configure. Only used to decide whether to *flag* a
# record: a miss costs a human glance, never a dropped record.
GEO_CODES = {
    "united kingdom": ("uk", "gb"), "ireland": ("ie",), "netherlands": ("nl",),
    "germany": ("de",), "france": ("fr",), "spain": ("es",), "italy": ("it",),
    "belgium": ("be",), "switzerland": ("ch",), "austria": ("at",),
    "portugal": ("pt",), "poland": ("pl",),
    "nordics": ("se", "no", "dk", "fi", "is"),
    "sweden": ("se",), "norway": ("no",), "denmark": ("dk",), "finland": ("fi",),
    "australia": ("au",), "new zealand": ("nz",), "canada": ("ca",),
    "united states": ("us", "usa"), "united arab emirates": ("ae",),
    "india": ("in",), "pakistan": ("pk",), "croatia": ("hr",), "serbia": ("rs",),
    "slovenia": ("si",),
}


def geo_tokens(geo):
    geo = str(geo).strip().lower()
    return (geo,) + GEO_CODES.get(geo, ())


def places_of(rec):
    """Where this company appears to be, from the trimmed facts."""
    facts = rec.get("company_facts") or {}
    parts = [str(o) for o in (facts.get("offices") or [])]
    for field in ("hq", "location", "country"):
        if facts.get(field):
            parts.append(str(facts[field]))
    return " ".join(parts).lower()


def mentions(places, geo):
    """A geo matches if its name or its country code appears as a whole word."""
    words = set(re.findall(r"[a-z]+", places))
    for token in geo_tokens(geo):
        if " " in token:
            if token in places:
                return True
        elif token in words:
            return True
    return False


def icp_flags(rec, config):
    """Section 4: out of geo and under size are flagged for a human call.

    Nothing here drops a record unless the client config explicitly sets
    flag_dont_drop to false.
    """
    market = config.get("market") or {}
    facts = rec.get("company_facts") or {}
    places = places_of(rec)
    flags = []

    for geo in market.get("exclude_geos") or []:
        if places and mentions(places, geo):
            flags.append(f"geo excluded by client: {geo}")

    allowed = market.get("geos") or []
    if allowed and places and not any(mentions(places, g) for g in allowed):
        flags.append("geo outside client's stated markets")

    size_min = market.get("size_min_employees")
    employees = facts.get("employees")
    if size_min and isinstance(employees, int) and employees < int(size_min):
        flags.append(f"{employees} employees, under the client minimum of {size_min}")
    return flags


def apply_icp(rec, config):
    """Record the flags. Drop only if the client asked for that explicitly."""
    flags = icp_flags(rec, config)
    facts = rec.setdefault("company_facts", {})
    if flags:
        facts["icp_flags"] = flags
        store.log(rec, "icp", "; ".join(flags))
    elif "icp_flags" in facts:
        facts.pop("icp_flags")

    market = config.get("market") or {}
    flag_dont_drop = market.get("flag_dont_drop", True)
    if flags and flag_dont_drop is False and rec.get("state") not in ("dropped", "pushed"):
        rec["state"] = "dropped"
        rec["drop_reason"] = flags[0]
        store.log(rec, "dropped", flags[0])
    return flags


def select(rec, config=None):
    """Persona and contact selection for one record. Lane aware."""
    config = config or clients.load(rec.get("client"))
    identity.assign_keys(rec.get("contacts") or [])
    apply_icp(rec, config)

    lane = rec.get("lane")
    if lane == "domains":
        # Before the cap is applied, not after: a contact whose exclusion
        # reason has stopped being true is a candidate like any other, and
        # must compete for the cap rather than be appended past it.
        readmit(rec, config)
        identity.assign_keys(rec.get("contacts") or [])
        keep, excluded = select_domains(rec, config)
    elif lane == "revive":
        keep, excluded = select_thread(rec, config, "no address or profile on the thread")
    else:
        keep, excluded = select_thread(rec, config, "not the person the signal names")

    kept_ids = {id(c) for c in keep}
    rec["contacts"] = keep
    for entry in excluded:
        if entry not in (rec.get("excluded") or []):
            rec.setdefault("excluded", []).append(entry)

    for contact in keep:
        contact["primary"] = False
    for contact in sorted(keep, key=lambda c: (0 if c.get("sendable") else 1,
                                               c.get("key") or "")):
        if contact.get("sendable"):
            contact["primary"] = True
            break

    store.log(rec, "personas",
              f"{len(keep)} kept, {len(excluded)} excluded",
              personas=[c.get("persona") for c in keep])
    for contact in keep:
        events.record(rec, events.PERSONA_SELECTED, contact_key=contact.get("key"),
                      persona=contact.get("persona"), angle=contact.get("angle"))
    return {"kept": keep, "excluded": excluded, "unused": kept_ids and None}


# ------------------------------------------------------------- the export

def export_dir(domain, root=None):
    """Honours the OUT override, exactly as render.py does."""
    return os.path.join(root or store.out_dir(), "domains", domain)


def export(rec, root=None):
    """out/domains/<domain>/: company.json, people.json, people.csv, cadence.json."""
    if rec.get("lane") != "domains":
        return None
    path = export_dir(rec["domain"], root)
    os.makedirs(path, exist_ok=True)

    company = {"name": rec.get("company"), "domain": rec.get("domain"),
               **(rec.get("company_facts") or {})}
    people = {"people": [{k: c.get(k) for k in
                          ("key", "name", "title", "persona", "angle", "linkedin",
                           "email", "email_source", "verdict", "sendable")}
                         for c in rec.get("contacts") or []],
              "excluded": rec.get("excluded") or []}

    with open(os.path.join(path, "company.json"), "w", encoding="utf-8") as f:
        json.dump(company, f, indent=2, ensure_ascii=False)
    with open(os.path.join(path, "people.json"), "w", encoding="utf-8") as f:
        json.dump(people, f, indent=2, ensure_ascii=False)
    with open(os.path.join(path, "people.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "name", "title", "persona", "angle", "email", "verdict",
                    "sendable", "linkedin"])
        for c in rec.get("contacts") or []:
            w.writerow([c.get("key"), c.get("name"), c.get("title"), c.get("persona"),
                        c.get("angle"), c.get("email"), c.get("verdict"),
                        c.get("sendable"), c.get("linkedin")])
    with open(os.path.join(path, "cadence.json"), "w", encoding="utf-8") as f:
        json.dump(rec.get("cadence") or {}, f, indent=2, ensure_ascii=False)
    return path


def run(apply=False, do_export=False, ids=None, lane=None):
    recs = store.load()
    configs = {}
    report = []
    for rec in recs:
        if ids and rec["id"] not in ids:
            continue
        if lane and rec.get("lane") != lane:
            continue
        if rec.get("state") in ("dropped", "pushed"):
            continue
        client = rec.get("client")
        if client not in configs:
            try:
                configs[client] = clients.load(client)
            except clients.ConfigError as e:
                # One record with a missing client config must not abort the
                # batch: the others still have work to do.
                configs[client] = None
                report.append({"id": rec["id"], "domain": rec.get("domain"),
                               "lane": rec.get("lane"), "kept": [],
                               "excluded": [], "skipped": str(e)})
                continue
        if configs[client] is None:
            report.append({"id": rec["id"], "domain": rec.get("domain"),
                           "lane": rec.get("lane"), "kept": [], "excluded": [],
                           "skipped": f"no config for client {client}"})
            continue
        working = rec if apply else json.loads(json.dumps(rec))
        result = select(working, configs[client])
        entry = {"id": rec["id"], "domain": rec.get("domain"), "lane": rec.get("lane"),
                 "kept": [{"name": c.get("name"), "persona": c.get("persona"),
                           "angle": c.get("angle"), "key": c.get("key")}
                          for c in result["kept"]],
                 "excluded": result["excluded"]}
        if apply and do_export:
            entry["export"] = export(rec)
        report.append(entry)
    if apply:
        store.save(recs)
    return {"applied": apply, "records": report}


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m src.personas")
    p.add_argument("--apply", action="store_true", help="write the selection to the queue")
    p.add_argument("--export", action="store_true", dest="do_export",
                   help="write out/domains/<domain>/ (needs --apply)")
    p.add_argument("--lane")
    p.add_argument("--id", action="append", dest="ids")
    a = p.parse_args(argv)

    result = run(apply=a.apply, do_export=a.do_export, ids=a.ids, lane=a.lane)
    head = "APPLIED" if a.apply else "DRY RUN, queue untouched"
    print(f"{head}: {len(result['records'])} record(s)")
    for r in result["records"]:
        print(f"\n  {r['id']} ({r['lane']}, {r['domain']})")
        for c in r["kept"]:
            print(f"    keep     {c['key']:<24} {str(c['persona']):<16} "
                  f"angle={c['angle']}  {c['name']}")
        for e in r["excluded"]:
            print(f"    exclude  {str(e.get('name')):<24} {e.get('why')}")
        if r.get("export"):
            print(f"    exported {r['export']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
