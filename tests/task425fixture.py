#!/usr/bin/env python3
"""ONE Productive account, built from real structure and carrying no real data.

`TASK-425`. The one-account dry run needs an account it can change one variable
of at a time, four times, and see the difference downstream. That is only
possible if the account is fixed, so it lives here rather than being assembled
inside the harness: a fixture written inline in a script is a fixture that
drifts between runs, and a matrix whose baseline drifts proves nothing.

## NOTHING HERE IS A REAL COMPANY OR A REAL PERSON

The brief permits a real public domain and forbids a real person. This file
takes the stricter half of that permission and uses a RESERVED domain as well,
for two measured reasons rather than caution:

  - `tests/test_fixture_hygiene.py` requires every email address in every
    tracked file to sit on a reserved suffix, and every contact here has an
    address;
  - the CLIENT'S OWN DOMAIN is already two of the suite's known baseline
    failures (`docs/PRODUCTION-HANDOFF-2026-09-28-NIGHT.md` section 5: the
    client's own domain and the approved CTA, correctly not a leak). Adding a
    third occurrence to a NEW tracked file would raise a standing baseline count
    for no gain - and this paragraph deliberately does not spell that domain
    out, because `test_fixture_hygiene` scans every tracked byte and a comment
    explaining the rule would break it. The run does not need a resolvable
    domain either: `packfacts` admits a fact by comparing the fact's host to the
    record's own `domain`, and two reserved hosts compare exactly as two real
    ones do.

What IS real is the SHAPE: an agency-shaped ICP record with an explicit ICP
verdict, three decision makers across two personas, research rows read off the
account's own site, and the six client-CSV fields under `company_facts` with
their batch file and row. That is what a record ingested from the 09-07 CSV and
then crawled actually looks like.

## THE TWO PROVENANCE CLASSES ARE BOTH PRESENT, ON PURPOSE

`RESEARCH` is the account's own site text. `packfacts.pack_for` ADMITS it, so
it is the only thing that can license a prospect-facing claim.

`COMPANY_FACTS` is the client's own approved list. Operator decision B,
2026-09-28: those six keys inform qualification, segmentation, strategy and
offer selection and license NO prospect-facing claim through either validation
path. `pack_for` returns them under `unused[CLIENT_SUPPLIED]` and keeps them
out of `pack["facts"]`.

Both are here because criterion 4 has to show "the exact claim licensed" and
trace it to admitted research rather than to the CSV. A fixture carrying only
admitted research could not tell the two apart, and a fixture carrying only CSV
facts could license nothing at all.

`headcount` is a FIGURE deliberately. It is the one value that makes the
half-enforced state of that decision observable: the pack path keeps it out of
the claim licence, and `src/claims.py` - a second, independent claim gate whose
support model is every `company_facts` key and value - still licenses it
(`ISSUE-048`, open). A fixture with no figure would make both gates look
equally strict.
"""

COMPANY = "Brightmoor Studio"
DOMAIN = "brightmoor.test"

#: The campaign id this account's dry run is staged under. One campaign, built
#: by this run, so it gets the canonical five-plus-five rather than one of the
#: 60 stale stored declarations (`docs/OPERATING-MODE.md`, launch blocker 9).
CAMPAIGN_ID = "task425-brightmoor"
RECORD_ID = "task425-brightmoor-studio"

#: The client CSV row this record was ingested from. The FILE and the ROW, both,
#: because `packfacts.batch_provenance` reports `UNKNOWN` for a row nobody
#: captured and a fixture that omitted it would be exercising the absent case.
BATCH = {"source": "batches/productive-2026-09-07.csv", "row": 412}

#: THE SIX CLIENT_SUPPLIED KEYS. `packfacts.INGEST_FACT_KEYS` exactly - not a
#: subset - so the artifact can show all six arriving as CLIENT_SUPPLIED and
#: none of them reaching the claim licence.
COMPANY_FACTS = {
    "headline": "product design and engineering for healthcare teams",
    "industry": "design and development agency",
    "headcount": "48",
    "employee_range": "26 to 50",
    "headcount_growth_12m": "9",
    "products": "product design, engineering, ongoing support",
}

#: THE ACCOUNT'S OWN RESEARCH, read off its own site, and therefore the only
#: thing here that can license a claim.
#:
#: Each row states its `source_url` on the account's own host and is STAMPED
#: with the record id, which is the stronger of the two admissions
#: `packfacts.identity_of` offers: an unstamped row is admitted on host alone,
#: and a fixture admitted for the weaker reason would not prove the stronger
#: path works.
#:
#: WRITTEN AGAINST THE LINT, NOT FOR PROSE. `copylint._traces` binds a specific
#: to the pack SENTENCE containing it and requires two shared content words with
#: the draft sentence (`TASK-330`). So each sentence here carries the words a
#: grounded opener would repeat, and the quoted phrase the copy leans on
#: appears verbatim in one of them. Remove that row and the claim stops tracing,
#: which is exactly what matrix run D measures.
#: IT HAS TO READ AS THE ICP, and the first attempt did not. Productive's
#: structural ICP is a services business that tracks time
#: (`config/clients/productive.yaml`, `icp.structural.company_types`), and the
#: `signal_verification` stage asks a model "is this an agency". The first
#: version of row one said the account "builds and runs digital products",
#: which reads as a product company: measured 2026-09-28, the stage answered
#: `is_agency: false`, the contact was held at `UNQUALIFIED` after two model
#: calls, and no copy existed to measure anything against. The wording now names
#: the agency, the client work and the market, which is what a real record of
#: this kind carries - and the hold was the gate being right about a bad
#: fixture, not a defect.
#: AND IT HAS TO SCORE USABLE, which is the second thing the first version got
#: wrong. `evidence.quality` refuses anything under `MIN_RELEVANCE` (0.65), and
#: `relevance` awards 0.25 for an operational term, 0.35 for a dated company
#: CHANGE, 0.10 for a figure and 0.10 x recency. Sentences that merely described
#: the agency scored 0.348 and came back `unusable`, so `research.for_prompt`
#: returned nothing. Every row below therefore carries what the scorer is
#: actually looking for - an operational subject, a change, and a figure - which
#: is not gaming it: the rows this system admits ARE the operational ones, and a
#: dated change is what its own comment calls "the whole why now the system
#: exists to find".
RESEARCH = (
    {"fact": "Brightmoor Studio is a product design and engineering agency in "
             "Amsterdam that launched its healthcare practice in 2016 and runs "
             "project delivery for those clients on retained monthly "
             "engagements.",
     "source_url": "https://brightmoor.test/about"},
    {"fact": "Brightmoor Studio says it has moved to 2 week delivery cycles "
             "across concurrent client projects, with resourcing decided a "
             "sprint ahead.",
     "source_url": "https://brightmoor.test/how-we-work"},
    {"fact": "Brightmoor Studio is hiring a delivery lead and says project "
             "resourcing across concurrent client work is the reason.",
     "source_url": "https://brightmoor.test/careers"},
)

#: WHICH RESEARCH ROW MATRIX RUN D REMOVES, and the phrase that stops tracing
#: when it goes. Named rather than indexed so the harness cannot silently remove
#: a different row than the artifact says it removed.
EVIDENCE_UNDER_TEST = "https://brightmoor.test/about"
CLAIM_UNDER_TEST = "retained monthly engagements"

#: WHAT MATRIX RUN B CHANGES: one fact, and one only. The replacement states a
#: different operating shape for the same account, so the angle a strategy can
#: honestly take changes with it. Everything else - the company, the domain, the
#: contacts, the offers, the client config, the cadence - is held constant.
FACT_CHANGED_B = {
    "fact": "Brightmoor Studio is a product design and engineering agency in "
            "Amsterdam that launched its healthcare practice in 2016 and runs "
            "project delivery for those clients on fixed price project work.",
    "source_url": "https://brightmoor.test/about",
}

#: THREE DECISION MAKERS, TWO PERSONAS, AND NO REAL PEOPLE.
#:
#: The first names are the convention this suite already uses for a placeholder
#: person (`Ada`, `Grace` in `test_staging_a_campaign_twice_builds_one`), and
#: the surname is `Tester` for the same reason: a fixture person should be
#: unmistakable as one. Addresses are on the reserved domain.
#:
#: TWO PERSONAS IN THE BASELINE IS THE CONTROL FOR MATRIX RUN C. That run flips
#: ONE contact from `economic_buyer` to the operations persona and nothing else,
#: so the other two contacts are the held-constant comparison inside the same
#: run: if their offer or capabilities move as well, the change was not caused
#: by the variable.
#:
#: `persona` is the key `cadence.product_words` and
#: `generate_campaign._select_offers` both read, and the two values are the only
#: two `config/clients/productive.yaml` declares under
#: `product.capability_by_persona`.
PERSONA_ECONOMIC_BUYER = "economic_buyer"
PERSONA_OPERATIONS = "champion"

#: The contact the matrix is driven on, and the one run C flips. Named so the
#: artifact and the harness cannot disagree about which one moved.
#:
#: THE ACCOUNT CARRIES THREE DECISION MAKERS AND THE MATRIX IS DRIVEN ON ONE, and
#: that is not a shortcut. "Same account, everything else constant" includes WHO
#: the copy is for: the first full matrix let the outer regeneration loop stop as
#: soon as ANY contact got through, so run A landed on the Managing Director and
#: its own control landed on the Head of Delivery, and the copy diff between a run
#: and its control was every step - for no reason that was about the system.
#:
#: Driving all three through every run instead is the other way to fix it, and it
#: costs about three times the model calls per invocation for no additional
#: causal evidence: the strategy is decided once per segment and persona, and each
#: contact's extract, hypothesis, match and writer prompts are independent of the
#: others. So the matrix compares one person across five runs, and the account
#: still has the buying committee the brief asks for.
CONTACT_UNDER_TEST = "task425-brightmoor-studio-c1"

def verification_evidence(email):
    """Two providers agreeing, stored as NORMALISED evidence.

    `sendable: True` ON THE CONTACT IS NOT READ BY ANYTHING THAT DECIDES.
    `verification.is_sendable` is the single authority and it RECOMPUTES from the
    evidence list every time, deliberately, so that nothing which can write a
    state string can make an address sendable without a provider having said so.
    Productive's own policy (`config/clients/productive.yaml`) names
    `deliverable` primary, `reoon` secondary and requires TWO confirmations, and
    it does not clear on the secondary alone.

    MEASURED, 2026-09-28: with `sendable: True` and `verified: True` and no
    evidence, `lint.sendable` was False, so `generate._candidate_steps` built NO
    email candidates at all - the run stored four LinkedIn notes and zero emails
    and reported no error. The email half of the artifact was simply missing, and
    nothing said why. That is the gate being right about a fixture that had never
    been verified by anybody.

    The evidence is a FIXTURE and says so in its own `reason`. No provider was
    called: `verification.result` is a pure constructor and this file performs no
    I/O.
    """
    from src import verification as _verification

    return {"evidence": [
        _verification.result("deliverable", "valid", email, deliverable=True,
                             charged=False,
                             reason="TASK-425 fixture, no provider was called"),
        _verification.result("reoon", "valid", email, safe_to_send=True,
                             deliverable=True, score=95, charged=False,
                             reason="TASK-425 fixture, no provider was called"),
    ]}


CONTACTS = (
    {"key": "task425-brightmoor-studio-c1",
     "email": "ada@brightmoor.test",
     "first_name": "Ada", "last_name": "Tester",
     "name": "Ada Tester",
     "title": "Managing Director",
     "persona": PERSONA_ECONOMIC_BUYER,
     "linkedin": "https://www.linkedin.com/in/ada-tester-brightmoor/",
     "sendable": True, "verified": True},
    {"key": "task425-brightmoor-studio-c2",
     "email": "grace@brightmoor.test",
     "first_name": "Grace", "last_name": "Tester",
     "name": "Grace Tester",
     "title": "Finance Director",
     "persona": PERSONA_ECONOMIC_BUYER,
     "linkedin": "https://www.linkedin.com/in/grace-tester-brightmoor/",
     "sendable": True, "verified": True},
    {"key": "task425-brightmoor-studio-c3",
     "email": "hedy@brightmoor.test",
     "first_name": "Hedy", "last_name": "Tester",
     "name": "Hedy Tester",
     "title": "Head of Delivery",
     "persona": PERSONA_OPERATIONS,
     "linkedin": "https://www.linkedin.com/in/hedy-tester-brightmoor/",
     "sendable": True, "verified": True},
)


#: Which page each row was read off, as the crawler records it. `evidence.make`
#: does not set `field` - `research.py`'s crawl adds it, on 1,137 of the 1,198
#: rows in the production store - and it is what `copyprompts._numbered` prints
#: as the source block's label.
_FIELD_OF = {
    "https://brightmoor.test/about": "about",
    "https://brightmoor.test/how-we-work": "how-we-work",
    "https://brightmoor.test/careers": "careers",
}


def research_rows(record_id=RECORD_ID, rows=RESEARCH):
    """`RESEARCH` as canonical evidence rows, scored, stamped for one record.

    BUILT THROUGH `evidence.make`, NOT BY HAND, and the first version of this
    file was the reason. `rec["research"]` is a LIST OF `evidence.make` ROWS
    (`SCHEMA.md`), and `generate._account_sources` reads it through
    `research.for_prompt` -> `evidence.select` -> `evidence.usable`, which keeps
    only rows whose `quality` is in `evidence.USABLE`. A hand-written row carries
    no `quality` at all, so it is dropped: measured 2026-09-28,
    `research.for_prompt` returned `[]` for this account, the ICP stage was
    handed no sources, answered "not an agency: insufficient information
    provided", and the contact was held `UNQUALIFIED` after two model calls.
    A fixture whose pack quietly becomes empty is worse than one that fails.

    `published_at` is STAMPED AT CALL TIME, seven days back, because
    `evidence.select` re-ages every row against the real clock and past the
    policy's maximum age `quality` caps at WEAK however relevant the fact is. A
    literal date here would stop reaching a prompt on some future day and the
    run would silently measure nothing.

    It ASSERTS the row is usable rather than hoping, for the same reason
    `tests.base.canonical_research` does.
    """
    import time

    from src import evidence as _evidence

    published = time.strftime("%Y-%m-%d",
                              time.gmtime(time.time() - 7 * 86400))
    out = []
    for row in rows:
        made = _evidence.make(
            fact=row["fact"], source_url=row["source_url"],
            source_type="crawl", provider="free-crawler",
            record_id=record_id, published_at=published,
            retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00",
                                       time.gmtime()))
        made["field"] = _FIELD_OF.get(row["source_url"], "site")
        if made["quality"] not in _evidence.USABLE:
            raise AssertionError(
                "this fixture exists to REACH a prompt, and `evidence.select` "
                "passes only %s rows: %r scored quality=%r relevance=%r"
                % (sorted(_evidence.USABLE), row["source_url"],
                   made.get("quality"), made.get("relevance_score")))
        out.append(made)
    return out


def record(record_id=RECORD_ID, *, research=None, contacts=None,
           company_facts=None):
    """The account as one canonical record. No cadence and no copy.

    Copy is NOT part of this fixture, deliberately. The whole point of the
    matrix is that copy is DERIVED: it comes out of
    `generate_campaign.generate()` reading these facts, this persona and the
    offer that persona selects. A fixture carrying authored copy would make
    every run's copy identical by construction and criterion 1 unfalsifiable -
    which is the shape `TASK-364`'s first attempt was rejected for.

    `state` is `ready` because `lint.UNSHIPPABLE` holds only `dropped` and
    `pushed`, and the ICP verdict is written EXPLICITLY rather than scored: real
    scoring reaches `review` at best (`tests.base.qualify_everything` says so),
    and tuning a fixture until it scored `qualified` would turn this into a test
    of the ICP model.
    """
    from src import icp as _icp

    return {
        "id": record_id,
        "client": "productive",
        "domain": DOMAIN,
        "company": COMPANY,
        "state": "ready",
        "batch": dict(BATCH),
        "qualification": {"verdict": {"icp_status": _icp.QUALIFIED}},
        "company_facts": dict(COMPANY_FACTS if company_facts is None
                              else company_facts),
        "research": research_rows(record_id,
                                  RESEARCH if research is None else research),
        "contacts": [
            dict(contact,
                 verification=verification_evidence(contact.get("email")))
            for contact in (CONTACTS if contacts is None else contacts)],
    }


def account(rec):
    """The record as `generate_campaign.generate()`'s `account` argument.

    `sources` is the account's ADMITTED pack and not `rec["research"]` raw, so
    a research row `packfacts` refuses for identity cannot reach a prompt. That
    is the same rule the copy lint enforces one gate later, applied at the point
    the words are written rather than after.
    """
    from src import packfacts as _packfacts

    pack, _unused = _packfacts.pack_for(rec)
    return {
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "segment": "all",
        "sources": [{"label": "site", "url": fact.get("source_url"),
                     "text": fact.get("snippet")}
                    for fact in pack.get("facts") or ()],
    }


def generate_contacts(rec):
    """The record's contacts in the shape `generate_campaign.generate()` reads.

    `contact_key` rather than `key`, and `sender_name` left absent so
    `_process_contact` falls back to the client config's own sender. Inventing a
    sender name here would put a name nobody chose at the top of every prompt.
    """
    out = []
    for contact in rec.get("contacts") or ():
        out.append({
            "contact_key": contact.get("key"),
            "email": contact.get("email"),
            "first_name": contact.get("first_name"),
            "last_name": contact.get("last_name"),
            "title": contact.get("title"),
            "linkedin": contact.get("linkedin"),
            "persona": contact.get("persona"),
        })
    return out
