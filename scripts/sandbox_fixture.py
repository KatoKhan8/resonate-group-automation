#!/usr/bin/env python3
"""Synthetic prospects for the phase-2 sandbox, in the shape the real flow reads.

WHY THIS FILE EXISTS
====================
`docs/SANDBOX-PHASE2-SURVEY-2026-10-12.md` names a second lane building
`scripts/sandbox_fixture.py` on `task-sandbox-fixture-2026-10-12`. Checked
2026-10-12 with `git fetch origin` and `git log`: that branch exists locally
but points at master `2bf7b8a5` and carries **no sandbox files at all**, and it
is not on the remote. So this is a minimal conforming fixture written to the
survey's spec so the run is not blocked. If the other lane lands, prefer theirs
and delete this; the runner takes `--fixture <path>` for exactly that reason.

EVERY SHAPE HERE WAS FORCED BY THE REAL FLOW REFUSING THE PREVIOUS ONE
======================================================================
Each of these is a measurement, not a preference. The survey recorded four of
them; running the flow against Productive's actual client config forced three
more, and those three CORRECT the survey:

1. **The cadence is not `cadence.STEPS`.** The survey says the record key is
   `rec["cadence_steps"]`. It is not a record key: `cadence.steps_for` reads
   `(campaign or {}).get(CADENCE_KEY)`, and with no campaign it falls through
   to `_named_sequence(config)` and then `cadencelibrary.named(config["cadence"])`.
   Productive names `productive_li_heavy_v1`, which is TEN steps keyed
   `li1,em1,li2,em2,li3,em3,li4,em4,li5,em5` - not the module constant's seven
   `day1..day21`. A fixture that writes `rec["cadence_steps"]` changes nothing.

2. **Persona must be one the client config knows.** `cadence.template_vars`
   merges `product_words(contact, config)`, which resolves `{capability}` from
   `capability_by_persona`. Productive declares `champion` and
   `economic_buyer`. Any other persona raises
   `CadenceError: template needs 'capability'` from `cadence.render` on
   `rung3_champion` and `rung3_economic_buyer`.

3. **A generated step with no written words is ABSENT from the timeline.**
   `cadence.expand_step` returns None for a `generated` spec whose stored slot
   has no `body` (email) or `note` (linkedin), and `build` drops it unless the
   spec carries `requires`. Nine of Productive's ten steps are generated. So a
   fixture that supplies no copy produces a timeline of one step, and every
   measurement of the send path would be a measurement of nothing.

   The copy is therefore fixture data **rendered by the repository's own
   renderer from the repository's own templates** - `cadence.render` over
   `cadence.TEMPLATES` with `cadence.template_vars`, plus `optout.append_opt_out`
   - written into `rec["cadence"][contact_key][step_key]`, which is the exact
   slot the phase-5 writer writes. No model is called and nothing is invented.
   The email templates are chosen per step to satisfy the REAL word contract
   (`lint.STEP_WORD_CONTRACT`), measured rather than assumed:

       em1 60-90  comparable_proof        87/87 words (champion/economic_buyer)
       em2 45-90  comparable_proof_short  59/59
       em3 60-90  rung3_<persona>         88/86
       em4 45-90  close_<persona>         64/69
       em5 45-90  breakup                 77/82

   `persona_pain` (98/103) and `angle_shift_*` (129/131) FAIL their own
   contract and are deliberately not used on the email steps. That is a
   finding about the shipped templates, recorded in the report.

4. Record top-level keys are the survey's 23, the id field is `id`, the contact
   id field is `key`, and the profile field is `linkedin`.

5. `rec["research"]` is a LIST built by `evidence.make(...)`.
   `contact["personalization"]["selected_evidence_ids"]` links them.

6. Verification is supplied as EVIDENCE, two confirmations, because
   `verification.is_sendable` recomputes from evidence and ignores a stored
   `sendable` flag by design. Under `lint.policy_for_record` - which is the
   policy the real gates ask - that yields `sendable: true,
   confirmation_count: 2`. Two controls in `tests/test_sandbox_run.py` prove
   the policy is genuinely exercised rather than bypassed.

NO REAL DATA, AND BOTH DIRECTIONS ASSERTED
==========================================
Every domain ends `.invalid` (RFC 2606: guaranteed never to resolve, so a
leaked send has nowhere to go). Names are drawn from a fixed synthetic list.
`sandboxharness.real_client_domains()` is read from the estate's own files and
no generated domain may appear in it - asserted, not assumed.

    py -3 scripts/sandbox_fixture.py --seed 20261012 --out docs/sandbox/
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (cadence, clients, evidence, lint, optout,  # noqa: E402
                 sandboxharness, verification)

#: Synthetic surnames and forenames. A fixed list, so a seed reproduces a run.
FORENAMES = ("Ana", "Marko", "Ivana", "Luka", "Petra", "Josip", "Maja",
             "Filip", "Dora", "Nikola", "Lea", "Ivan", "Sara", "Tomislav",
             "Klara", "Davor", "Nina", "Bruno", "Tea", "Goran")
SURNAMES = ("Horvat", "Kovacic", "Babic", "Maric", "Juric", "Novak",
            "Vukovic", "Petrovic", "Matic", "Blazevic", "Pavlovic", "Radic",
            "Tomic", "Knezevic", "Bozic", "Lovric", "Perkovic", "Grgic",
            "Sain", "Vidovic")
COMPANY_WORDS = ("Northfield", "Brightmark", "Keelpoint", "Ambergate",
                 "Sixcastle", "Lowtide", "Quietriver", "Palegrove",
                 "Thornbury", "Stillwater", "Oakmere", "Finchley",
                 "Redhollow", "Greystone", "Marlowe", "Hartwell",
                 "Dunmore", "Castleford", "Ravensworth", "Elmstead")
COMPANY_SUFFIX = ("Studio", "Collective", "Works", "Partners", "Agency",
                  "Group", "Labs", "Digital")

#: Titles that the client config's routing actually recognises, split by the
#: two personas the config declares. A title outside these is not wrong, but it
#: would route to no persona and the capability sentence would not resolve.
CHAMPION_TITLES = ("Head of Operations", "Operations Manager",
                   "Operations Director", "Head of Delivery",
                   "Project Manager", "Head of Resourcing",
                   "Studio Manager", "Head of Production")
BUYER_TITLES = ("Chief Financial Officer", "Head of Finance",
                "Finance Director", "Managing Director",
                "Chief Operating Officer", "Founder")

#: Angles the client config labels. Read from `angle_labels` at build time;
#: this is the fallback order so a seed is stable if the config gains keys.
ANGLE_ORDER = ("ops", "delivery", "finance", "resource_management",
               "operations", "founder")

#: Which template renders each generated step, per channel. Measured against
#: `lint.STEP_WORD_CONTRACT` - see the module docstring.
EMAIL_TEMPLATE_FOR_STEP = {
    "em1": "comparable_proof",
    "em2": "comparable_proof_short",
    "em3": "rung3_{persona}",
    "em4": "close_{persona}",
    "em5": "breakup",
}
#: LinkedIn notes have a character bound, not a word contract. Only two note
#: templates ship, so the fixture varies the note by the EVIDENCE FACT it
#: cites - one fact per step, from the record's own `research` list. That keeps
#: every sentence traceable to something on the record and still gives the
#: duplicate detector distinct bodies to judge.
LI_NOTE_TEMPLATE = {"li1": "linkedin_intro"}
LI_FOLLOWUP_TEMPLATE = "linkedin_followup"

#: Facts are written WITHOUT a number or a month on purpose. `claims.is_claim`
#: examines a sentence only when it carries one, and a fixture that tripped the
#: claim checker would be measuring the fixture's prose rather than the flow.
FACT_SHAPES = (
    "{company} opened a second delivery studio and moved resourcing onto a "
    "weekly planning cycle",
    "{company} is hiring project managers and a resource manager for the "
    "{sector} side of the business",
    "{company} now reports project margin to its board every month instead "
    "of at the end of each engagement",
    "{company} consolidated time tracking and invoicing after running them "
    "in separate tools",
)

PERSONAS = ("champion", "economic_buyer")

#: The 23 top-level record keys the survey measured. Asserted on every record
#: this module emits, so a key added or dropped here fails loudly rather than
#: silently changing what the flow reads.
RECORD_KEYS = ("id", "domain", "client", "batch", "company", "lane", "signal",
               "state", "stages", "events", "log", "excluded", "drop_reason",
               "hook", "context", "diagnosis", "waterfall", "sizing",
               "qualification", "company_facts", "research", "contacts",
               "cadence")

#: The 15 contact keys the survey measured, plus `personalization`, which the
#: survey names separately as a requirement.
CONTACT_KEYS = ("key", "name", "email", "linkedin", "persona", "title",
                "primary", "angle", "email_source", "sendable", "mx", "reoon",
                "verdict", "verification", "bison_lead_id", "personalization")


class FixtureRefused(RuntimeError):
    """The fixture could not be built without breaking one of its own rules."""


def _slug(text):
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")


def _company_name(rng, index):
    return "%s %s" % (rng.choice(COMPANY_WORDS), rng.choice(COMPANY_SUFFIX))


def _email(forename, surname, domain):
    return "%s.%s@%s" % (forename.lower(), surname.lower(), domain)


def build_record(rng, index, client, batch, config, today, sector_pool):
    """One synthetic company with its contacts, copy and evidence."""
    rid = "sbx-%04d" % index
    company = _company_name(rng, index)
    domain = "%s-%04d.invalid" % (_slug(company.split()[0]), index)
    sector = rng.choice(sector_pool)
    employees = rng.choice((18, 24, 35, 48, 60, 72, 95, 120, 160))

    rec = {
        "id": rid,
        "domain": domain,
        "client": client,
        "batch": batch,
        "company": company,
        "lane": "cold",
        "signal": "weekly resourcing cycle",
        "state": "approved",
        "stages": {},
        "events": [],
        "log": [],
        "excluded": False,
        "drop_reason": None,
        "hook": "a second delivery studio",
        "context": "%s agency, %d people" % (sector, employees),
        "diagnosis": {},
        "waterfall": {},
        "sizing": {},
        "qualification": {"verdict": "accept",
                          "why": ["synthetic sandbox fixture: accepted so the "
                                  "send path is the thing under test"]},
        "company_facts": {"employees": employees, "industry": sector},
        "research": [],
        "contacts": [],
        "cadence": {},
    }

    # Evidence first: the contacts' `selected_evidence_ids` point at it, and
    # the LinkedIn notes cite it.
    angle_words = ["utilisation", "margin", "capacity", "resourcing",
                   "budget", "profitability"]
    for n, shape in enumerate(FACT_SHAPES):
        rec["research"].append(evidence.make(
            fact=shape.format(company=company, sector=sector),
            source_url="https://%s/news/%d" % (domain, n),
            source_type="company_news",
            provider="sandbox",
            record_id=rid,
            published_at=_days_before(today, 6 + 3 * n),
            subject=evidence.COMPANY,
            persona=PERSONAS[n % len(PERSONAS)],
            angle_words=angle_words,
            today=today))
    evidence_ids = [item["evidence_id"] for item in rec["research"]]

    angles = [a for a in ANGLE_ORDER
              if a in (config.get("angle_labels") or {})] or list(ANGLE_ORDER)
    for i in range(3):
        forename = FORENAMES[rng.randrange(len(FORENAMES))]
        surname = SURNAMES[rng.randrange(len(SURNAMES))]
        persona = PERSONAS[i % len(PERSONAS)]
        titles = CHAMPION_TITLES if persona == "champion" else BUYER_TITLES
        email = _email(forename, "%s%d" % (surname, i), domain)
        rec["contacts"].append({
            "key": "%s-c%d" % (rid, i),
            "name": "%s %s" % (forename, surname),
            "email": email,
            "linkedin": "https://www.linkedin.com/in/%s-%s-%s-c%d"
                        % (forename.lower(), surname.lower(), rid, i),
            "persona": persona,
            "title": rng.choice(titles),
            "primary": i == 0,
            "angle": angles[(index + i) % len(angles)],
            "email_source": "sandbox",
            # Written, and deliberately IGNORED by the gate that matters.
            # `verification.is_sendable` recomputes from the evidence below.
            "sendable": True,
            "mx": {"status": "allowed", "mx_provider": "google",
                   "mx_classification": "allowed",
                   "mx_records": ["aspmx.l.google.com",
                                  "alt1.aspmx.l.google.com"],
                   "checked_at": today},
            "reoon": None,
            "verdict": None,
            "verification": {"evidence": [
                verification.result("deliverable", verification.S_VALID, email,
                                    reason="synthetic sandbox fixture"),
                verification.result("reoon", verification.S_VALID, email,
                                    reason="synthetic sandbox fixture")]},
            "bison_lead_id": None,
            "personalization": {"selected_evidence_ids": list(evidence_ids),
                                "level": "company_fact"},
        })

    install_copy(rec, config)
    _assert_shape(rec)
    return rec


def _days_before(today, days):
    import datetime

    return (datetime.date.fromisoformat(today)
            - datetime.timedelta(days=days)).isoformat()


def install_copy(rec, config, sequence=None):
    """Write the client's own rendered copy into the slots the writer writes.

    Separated from `build_record` so the runner can re-install copy after a
    sequence change and so `tests/test_sandbox_run.py` can call it directly.
    """
    sequence = sequence or cadence.steps_for(None, config, rec, None)
    facts = [item["fact"] for item in rec.get("research") or []]
    for contact in rec.get("contacts") or []:
        key = lint.contact_key(contact)
        persona = contact.get("persona") or "champion"
        values = cadence.template_vars(rec, contact, config)
        slots = rec.setdefault("cadence", {}).setdefault(key, {})
        li_index = 0
        for spec in sequence:
            if not spec.get("generated"):
                continue
            step_key = spec["key"]
            if spec["channel"] == "email":
                name = EMAIL_TEMPLATE_FOR_STEP.get(step_key)
                if name is None:
                    raise FixtureRefused(
                        "no template chosen for email step %r; the word "
                        "contract was measured per step and a step this "
                        "module has not measured must not be guessed at"
                        % (step_key,))
                name = name.format(persona=persona)
                rendered = cadence.render(cadence.TEMPLATES[name], values)
                slots[step_key] = {
                    "channel": "email",
                    "subject": rendered.get("subject"),
                    "body": optout.append_opt_out(rendered.get("body")),
                    "generated": True,
                }
            else:
                name = LI_NOTE_TEMPLATE.get(step_key, LI_FOLLOWUP_TEMPLATE)
                rendered = cadence.render(cadence.TEMPLATES[name], values)
                note = (rendered.get("note") or "").strip()
                if facts:
                    cited = facts[li_index % len(facts)]
                    note = "%s (%s)" % (note, cited[:90].rstrip())
                li_index += 1
                slots[step_key] = {"channel": "linkedin",
                                   "note": note[:300],
                                   "generated": True}
    return rec


def _assert_shape(rec):
    missing = [k for k in RECORD_KEYS if k not in rec]
    extra = [k for k in rec if k not in RECORD_KEYS]
    if missing or extra:
        raise FixtureRefused(
            "record %s does not carry the measured key set: missing %s, "
            "unexpected %s" % (rec.get("id"), missing, extra))
    for contact in rec["contacts"]:
        cmissing = [k for k in CONTACT_KEYS if k not in contact]
        cextra = [k for k in contact if k not in CONTACT_KEYS]
        if cmissing or cextra:
            raise FixtureRefused(
                "contact %s does not carry the measured key set: missing %s, "
                "unexpected %s" % (contact.get("key"), cmissing, cextra))
        if not str(contact.get("linkedin") or "").startswith("https://"):
            raise FixtureRefused(
                "contact %s has no LinkedIn profile; the survey requires one "
                "on every record" % (contact.get("key"),))
    if not sandboxharness.is_synthetic_domain(rec["domain"]):
        raise FixtureRefused("domain %r is not synthetic" % (rec["domain"],))


def build(seed=20261012, companies=100, client="productive", batch="sandbox",
          today="2026-10-06", config=None):
    """`companies` records with three contacts each. Deterministic by seed."""
    config = config if config is not None else clients.load(client)
    rng = random.Random(seed)
    sector_pool = ("software development", "design", "digital marketing",
                   "creative services", "product engineering")
    recs = [build_record(rng, i + 1, client, batch, config, today, sector_pool)
            for i in range(companies)]
    assert_no_real_domains(recs)
    return recs


def assert_no_real_domains(recs, root=None):
    """BOTH DIRECTIONS. A synthetic suffix is not on its own a guarantee.

    `real_client_domains` is read from `config/suppress.local.txt` and the
    client file rather than from a literal list, so this tracks the estate.
    """
    real = sandboxharness.real_client_domains(root)
    hits = []
    for rec in recs:
        domain = str(rec.get("domain") or "").lower()
        if domain in real:
            hits.append(domain)
        for contact in rec.get("contacts") or []:
            tail = str(contact.get("email") or "").rsplit("@", 1)[-1].lower()
            if tail and tail in real:
                hits.append(tail)
    if hits:
        raise FixtureRefused(
            "a generated domain collides with a real one: %s"
            % ", ".join(sorted(set(hits))))
    return True


def summarise(recs):
    contacts = [c for r in recs for c in r.get("contacts") or []]
    personas = {}
    for c in contacts:
        personas[c.get("persona")] = personas.get(c.get("persona"), 0) + 1
    steps = sum(len(slots) for r in recs
                for slots in (r.get("cadence") or {}).values())
    return {"companies": len(recs), "contacts": len(contacts),
            "personas": personas, "copy_slots": steps,
            "evidence_items": sum(len(r.get("research") or []) for r in recs),
            "domains_synthetic": all(sandboxharness.is_synthetic_domain(
                r.get("domain")) for r in recs)}


def main(argv=None):
    p = argparse.ArgumentParser(prog="py -3 scripts/sandbox_fixture.py",
                                description=__doc__)
    p.add_argument("--seed", type=int, default=20261012)
    p.add_argument("--companies", type=int, default=100)
    p.add_argument("--client", default="productive")
    p.add_argument("--today", default="2026-10-06",
                   help="the simulated date the evidence is aged against")
    p.add_argument("--out", default=None,
                   help="directory to write fixture-seed-<N>.json into")
    a = p.parse_args(argv)

    recs = build(seed=a.seed, companies=a.companies, client=a.client,
                 today=a.today)
    print(json.dumps(summarise(recs), indent=2))
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        path = os.path.join(a.out, "fixture-seed-%d.json" % a.seed)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(recs, handle, indent=1, sort_keys=True)
        print("wrote %s" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
