#!/usr/bin/env python3
"""THE SELECTED REAL ACCOUNT for TASK-425's causal matrix, and its evidence.

`TASK-425` / `P0-C`. OPERATOR DECISION, Zvonimir, 2026-09-28: select a REAL
company from the estate's own source, through the normal qualification and
eligibility path, with independently verifiable PUBLIC evidence - and commit no
real personal data.

    account   Brand IQ          domain  brandiq.com
    record    brandiq-com       batch   productive-live-pilot-0050.csv
    claim     ISO 9001:2015     page    https://brandiq.com/about

## IT WAS SELECTED BY THE GATES, NOT BY TASTE

Measured 2026-09-28 over all 1,582 records in production's `work/queue.jsonl`
(`scratchpad` scan, reported in `docs/P0C-CAUSAL-FIXTURE-2026-09-28.md`):

    1,582  records
      113  `qualify.state_of` == qualified
       41  of those have NO sendable contact
       16  of those have fewer than two identity-admitted research rows
       11  are excluded as a known-forbidden domain or name
       43  carry no figure that one row licenses and another does not
        2  survive
        1  licenses a figure from a real operational fact rather than from a
           blog index's own post dates

Brand IQ is that one. **Nothing was relaxed to reach it**: the account arrives
through `qualify.state_of`, its ICP verdict is the stored one, its contact is
sendable by `verification.is_sendable`, and the only filters added on top are
"can run D actually remove something" and "is it safe to name in git".

## WHAT IS REAL, WHAT IS COMMITTED, AND WHY THEY ARE NOT THE SAME LIST

**The record is real and it is NOT in this file.** `record_from_store()`
returns the account exactly as the estate holds it - its stored ICP verdict,
its `company_facts`, its Apify-fetched research and its ONE sendable contact -
from `work/`, which is gitignored because it is real companies and real people.
The matrix runs on that. Nothing about the contact is copied here: not a name,
not an address, not a key, not a title.

**What IS committed is the account's public identity and its public evidence.**
`brandiq.com` is a company domain, the two source URLs are public pages, and
`tests/fixtures/task425-evidence.json` holds verbatim excerpts of those pages
re-verified against the LIVE site on 2026-09-28, with the http status, the
retrieval time and a sha256 of the text as read. A reader can open the URL and
check the sentence. That is what "independently verifiable" has to mean.

**The about page names four real executives** in its schema.org block, and the
estate's own research row for it carries all four, because the Apify extractor
took the whole page. So the row is not copied here either. The excerpts stored
are chosen sentences that carry none of them, and the choice was self-tested at
build time against every one of those names - and **that list of names is not
in this repository and must never be**: a guard that has to name real people in
order to protect them has retired itself.

**`RESEARCH` below is therefore a REDACTED RECONSTRUCTION**, built only from
the stored excerpts, and it exists for the offline tests and for a caller with
no access to the store. It is a strict subset of what the live page says. It is
NOT what the matrix should run on: `record_from_store()` is.

## THE CLAIM UNDER TEST, AND WHY IT IS THIS ONE

`CLAIM_UNDER_TEST` is `9001`, from "Brand IQ is ISO 9001:2015 certified". It is
a specific both claim gates can see (`copylint.specifics_in` returns it), it
appears in exactly ONE identity-admitted row, and that row is `strong` quality
so the writer is actually shown it.

Measured 2026-09-28 on the record as the store holds it, both gates, the same
second-person sentence:

    evidence present   copylint: licensed      claims: licensed
    evidence removed   copylint: ['9001','2015']
                       claims:  "the figure 9001 appears in no stored fact"
    negative control   an ISO number on no page of theirs is refused by both
                       WITH the full pack present

Removing the row leaves three admitted rows and one prompt-usable row, so run D
cannot be confounded with "the lead held because it had no research at all".

## WHY THE PREVIOUS FIXTURE COULD NOT MEASURE RUN D

It was an invented company, and its declared claim was the phrase
`retained monthly engagements`. That is not a checkable specific - no digit, no
quoted phrase, no capitalised multi-word name - so `copylint.untraceable` never
examined it, `claims.check` never examined it, the artifact's "exact claim
licensed" column was empty for all nine messages, and removing its research row
changed nothing either gate could see. Run D read NOT COMPARABLE for a reason
that had nothing to do with the copy engine: there was nothing to remove.

`tests/test_the_claim_under_test_is_load_bearing.py` asserts the property
mechanically now, so it cannot silently go missing again.
"""
import json
import os

COMPANY = "Brand IQ"
DOMAIN = "brandiq.com"

#: The record id the estate holds this account under. `record_from_store()`
#: reads it; it is not a person and it is not secret.
RECORD_ID = "brandiq-com"

#: The campaign id this account's dry run is staged under. One campaign, built
#: by this run, so it gets the canonical five-plus-five rather than one of the
#: 60 stale stored declarations (`docs/OPERATING-MODE.md`, launch blocker 9).
CAMPAIGN_ID = "task425-brandiq"

#: The batch the record was ingested from, recorded so the artifact can say
#: which source the account came through. NOT used to build anything: the
#: authority is the record's own `batch`, read from the store.
BATCH_SOURCE = "productive-live-pilot-0050.csv"

ABOUT = "https://brandiq.com/about"
HOME = "https://brandiq.com/"

#: The stored public pages every committed fact is grounded in.
EVIDENCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "fixtures", "task425-evidence.json")


def stored_evidence():
    """The stored pages: url, status, retrieval time, sha256 and excerpts."""
    with open(EVIDENCE_FILE, encoding="utf-8") as handle:
        return json.load(handle)


def excerpts_for(url):
    """The verbatim excerpts stored for one page, as a tuple."""
    for page in stored_evidence().get("pages") or ():
        if page.get("url") == url:
            return tuple(page.get("excerpt") or ())
    return ()


def _row(url, keep):
    """One reconstructed row: the stored excerpts for `url`, in order.

    `keep` selects by INDEX into the stored excerpt list rather than by
    retyping the sentences, so a reconstructed row cannot drift away from the
    evidence file: there is one copy of each sentence in this repository and it
    is the one that was verified against the live page.
    """
    excerpts = excerpts_for(url)
    return {"fact": " ".join(excerpts[i] for i in keep), "source_url": url}


#: THE ACCOUNT'S ADMITTED RESEARCH, RECONSTRUCTED FROM THE STORED EXCERPTS.
#: See the module docstring: the matrix runs on `record_from_store()`, and this
#: is the offline subset.
#:
#: Row 0 is the page the claim under test comes from and carries, in order:
#: what the firm is, the ISO 9001:2015 certification, and four dated expansion
#: and launch entries from the page's own timeline. Those give
#: `evidence.relevance` an operational subject, a company change and a figure,
#: which is what it scores and what a real operational row carries anyway.
RESEARCH = (
    _row(ABOUT, (0, 1, 2, 3, 4, 5, 8)),
    _row(HOME, (0, 1)),
)

#: WHICH ROW MATRIX RUN D REMOVES, and the claim that stops tracing when it
#: goes. Named rather than indexed so the harness cannot silently remove a
#: different row than the artifact says it removed.
EVIDENCE_UNDER_TEST = ABOUT
CLAIM_UNDER_TEST = "9001"

#: The claim as a second-person sentence, built out of the pack sentence's own
#: words. A SHORT sentence does not clear `copylint._traces`'s two-content-word
#: threshold and is refused even with the row present - that is the gate being
#: right rather than a fixture defect, and it is why the copy path needs its
#: retry loop.
#:
#: It is licensed and then refused IDENTICALLY on the real record and on the
#: offline reconstruction, which is what makes the committed test evidence
#: about the real account rather than about this file.
CLAIM_SENTENCE = ("You are ISO 9001:2015 certified, confirming a structured, "
                  "consistent and quality-driven approach to managing your "
                  "internal processes.")

#: THE NEGATIVE CONTROL. The same sentence with a certification number that is
#: on no page of theirs. If this were licensed, the gates would be passing
#: everything and nothing above would be evidence.
INVENTED_SENTENCE = CLAIM_SENTENCE.replace("9001:2015", "27701:2019")

#: WHAT MATRIX RUN B CHANGES: one fact, and one only.
#:
#: IT IS ANOTHER REAL FACT FROM THE SAME PAGE, not an invented one, and that is
#: the constraint a real account adds. The previous fixture could write any
#: replacement it liked because its company did not exist; fabricating a
#: different operating shape for a real firm would be exactly the invented
#: provenance the directives forbid. So B swaps the certification-and-expansion
#: shape for the recognition-and-scale shape the same page also states - the
#: Inc. 5000 nomination and the Martech Outlook award - which is a different
#: honest angle. It carries no `9001`, so run B also withdraws the claim under
#: test, and the artifact has to say so rather than report B as holding it
#: constant.
FACT_CHANGED_B = _row(ABOUT, (0, 9, 10, 6, 7, 11))

#: `2015` IS NOT THE CLAIM UNDER TEST. `copylint._traces` does a SUBSTRING
#: search over a normalised pack sentence (`ISSUE-055`, open, reported by
#: TASK-425 and deliberately NOT fixed here - tightening a claim gate is not
#: this task's licence), so a short token can trace against a longer number
#: that contains it. `9001` and `2015` both appear in exactly one row here and
#: both are refused when it goes, which is why the pair is reported together.
CLAIM_TOKENS_WITHDRAWN_WITH_IT = ("9001", "2015")

PERSONA_ECONOMIC_BUYER = "economic_buyer"
PERSONA_OPERATIONS = "champion"

#: THE PLACEHOLDER CONTACT, AND IT IS NOT THE PROSPECT.
#:
#: The account has exactly ONE contact and they are a real person, sendable,
#: filed under `economic_buyer` - which is what run C needs, since C's declared
#: intervention is economic buyer -> operations. None of their details is in
#: this file. `contact_under_test(rec)` resolves the real one from the record;
#: this placeholder exists so the offline tests can build a record at all, and
#: `tests/test_the_accounts_research_is_grounded_in_a_stored_page.py` asserts
#: it can never be mistaken for a real identity: the surname is `Tester` and
#: the address is on `p0c-fixture.test`, a suffix reserved by RFC 2606 which
#: cannot resolve and so cannot be mailed. It is deliberately NOT derived from
#: the account's real domain: `ada@brandiq.test` becomes a plausible real
#: address the moment somebody edits one character, and this account's real
#: mailboxes exist.
FIXTURE_MAIL_DOMAIN = "p0c-fixture.test"
CONTACT_UNDER_TEST = "task425-placeholder-c1"

CONTACTS = (
    {"key": CONTACT_UNDER_TEST,
     "email": "ada@" + FIXTURE_MAIL_DOMAIN,
     "first_name": "Ada", "last_name": "Tester",
     "name": "Ada Tester",
     "title": "Finance Director",
     "persona": PERSONA_ECONOMIC_BUYER,
     "linkedin": "https://www.linkedin.com/in/ada-tester-p0c/",
     "sendable": True, "verified": True},
)


def contact_under_test(rec):
    """The REAL eligible identity the matrix runs on, from the record.

    THE SAME PERSON ON EVERY SIDE, which is the property the previous matrix
    lost: its outer loop stopped as soon as ANY contact got copy through, so a
    run and its own control landed on different people and every step read as
    changed for no reason that was about the system.

    `verification.is_sendable` is the authority, not the contact's `sendable`
    string: the string can be written by anything, and the function recomputes
    from the provider evidence every time.
    """
    from src import verification as _verification

    for contact in rec.get("contacts") or ():
        if _verification.is_sendable(contact):
            return contact.get("key")
    return None


def record_from_store(record_id=RECORD_ID):
    """The account AS THE ESTATE HOLDS IT. The matrix runs on this.

    Its ICP verdict, its research, its `company_facts` and its one sendable
    contact are the real ones, so the account reaches the copy path through the
    gates rather than past them. Returns `None` when the store has no such
    record, which a caller must report rather than silently substitute
    `record()` for - the two are not the same account and a run that quietly
    fell back to the reconstruction would be measuring a different thing under
    the same name.
    """
    from src import store as _store

    return _store.get(record_id)


def verification_evidence(email):
    """Two providers agreeing, for the PLACEHOLDER contact only.

    `sendable: True` ON A CONTACT IS NOT READ BY ANYTHING THAT DECIDES.
    `verification.is_sendable` is the single authority and it RECOMPUTES from
    the evidence list every time, deliberately, so nothing that can write a
    state string can make an address sendable without a provider having said
    so. Productive's own policy names `deliverable` primary, `reoon` secondary
    and requires TWO confirmations.

    MEASURED, 2026-09-28: with `sendable: True`, `verified: True` and no
    evidence, `lint.sendable` was False, so `generate._candidate_steps` built
    NO email candidates at all - a run stored four LinkedIn notes, zero emails
    and reported no error.

    The evidence says in its own `reason` that it is a fixture. No provider was
    called, and none could be: the address is on a reserved suffix.
    """
    from src import verification as _verification

    return {"evidence": [
        _verification.result("deliverable", "valid", email, deliverable=True,
                             charged=False,
                             reason="P0-C placeholder, no provider was called"),
        _verification.result("reoon", "valid", email, safe_to_send=True,
                             deliverable=True, score=95, charged=False,
                             reason="P0-C placeholder, no provider was called"),
    ]}


def research_rows(record_id=RECORD_ID, rows=RESEARCH):
    """`RESEARCH` as canonical evidence rows, scored, stamped for one record.

    BUILT THROUGH `evidence.make`, NOT BY HAND. `rec["research"]` is a LIST OF
    `evidence.make` ROWS (`SCHEMA.md`), and `generate._account_sources` reads
    it through `research.for_prompt` -> `evidence.select` -> `evidence.usable`,
    which keeps only rows whose `quality` is in `evidence.USABLE`. A
    hand-written row carries no `quality` at all and is dropped, which is how a
    fixture's pack quietly becomes empty.

    `published_at` IS NONE, AND THAT IS THE HONEST VALUE. Neither page states a
    publication date, so there is none to record - and the estate's own rows
    for this account carry `published_at: None` for the same reason.
    `retrieved_at` is the real time of a real fetch.

    Only the row carrying the claim under test is ASSERTED usable. The
    homepage row is a short reconstruction of a page the estate holds in full,
    so it does not always clear `MIN_RELEVANCE` offline; that is recorded
    rather than papered over, and it is why the matrix runs on
    `record_from_store()`.
    """
    import time

    from src import evidence as _evidence

    out = []
    for row in rows:
        made = _evidence.make(
            fact=row["fact"], source_url=row["source_url"],
            source_type="crawl", provider="free-crawler",
            record_id=record_id, published_at=None,
            retrieved_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00",
                                       time.gmtime()))
        made["field"] = "about" if row["source_url"] == ABOUT \
            else "company_website"
        if row["source_url"] == EVIDENCE_UNDER_TEST \
                and made["quality"] not in _evidence.USABLE:
            raise AssertionError(
                "the row carrying the claim under test must REACH a prompt, "
                "and `evidence.select` passes only %s rows: it scored "
                "quality=%r relevance=%r"
                % (sorted(_evidence.USABLE), made.get("quality"),
                   made.get("relevance_score")))
        out.append(made)
    return out


def record(record_id=RECORD_ID, *, research=None, contacts=None,
           company_facts=None):
    """The OFFLINE RECONSTRUCTION. Deterministic, and not the real account.

    Its research is the redacted subset and its contact is the placeholder, so
    it can be built with no store and no network. Use it for tests. Use
    `record_from_store()` for the matrix.

    `state` is `ready` because `lint.UNSHIPPABLE` holds only `dropped` and
    `pushed`, and the ICP verdict is written EXPLICITLY here rather than
    scored - the REAL record's verdict is the stored one and is `qualified`
    with `icp_tier: C`, measured 2026-09-28.
    """
    from src import icp as _icp

    return {
        "id": record_id,
        "client": "productive",
        "domain": DOMAIN,
        "company": COMPANY,
        "state": "ready",
        "batch": {"source": BATCH_SOURCE, "row": "UNKNOWN"},
        "qualification": {"verdict": {"icp_status": _icp.QUALIFIED,
                                      "icp_tier": "C"}},
        "company_facts": dict(company_facts or {}),
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
    is the same rule the copy lint enforces one gate later, applied at the
    point the words are written rather than after.
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
    `_process_contact` falls back to the client config's own sender. Inventing
    a sender name here would put a name nobody chose at the top of every
    prompt.
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
