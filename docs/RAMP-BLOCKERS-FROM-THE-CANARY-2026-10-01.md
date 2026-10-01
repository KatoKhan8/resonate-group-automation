# Ramp blockers found while getting one canary out — 2026-10-01

Format: CLAIM / AUTHORITY / MEASURED AT / STATE. None of these blocks the
canary. Every one blocks the ramp, and each was measured rather than guessed.

No prospect PII in this file.

## 1. The ICP gate clears 11,690 accounts it cannot classify

    CLAIM      29.86% of everything the ICP gate calls QUALIFIED has no
               classifiable vertical at all
    AUTHORITY  src/icp.py:208 score over work/agency-sourcing.jsonl;
               src/segments.py:431 classify_vertical
    MEASURED   2026-10-01, 47,982 rows reaching the gate
    STATE      QUALIFIED 39,152 · of those vertical UNKNOWN 11,690 = 29.86%

    Commonest industries among the UNKNOWN:
        Advertising Services 7,814 · Design Services 2,130
        Marketing Services 1,367 · Software Development 329
        IT System Design Services 27

The gate leans almost entirely on the `industry` LABEL. Measured consequence,
6 of 6 on the first paid sourcing run: it passed a women's NETWORKING
ORGANISATION, a JOB BOARD, an advertising MAGAZINE and an ADTECH product for
monetising mobile games. One of them qualified because the word "advertising"
appears in its own sentence saying networking works better THAN advertising,
and `vertical_why` said so plainly - "only 1 weak signal: not enough to
classify". The system knew; the gate never asked it.

A free walk of 25 fresh candidates cut 9 of them (36%) on this rule alone.

**Fix:** make `segments.classify_vertical` a formal gate before any paid call.
It is free. It would have saved 30 of the first 66 credits spent. The standing
operator rule is already in OPERATING-MODE; this is about enforcing it in the
pipeline rather than in an agent's instructions.

## 2. `reveal_info=True` is hardcoded, and turning it off is NOT the fix

    CLAIM      enrichment burns phone credits no cost table prices, and the
               obvious remedy does not work
    AUTHORITY  src/enrich.py:1000 hardcodes reveal_info=True;
               src/providers/contactout.py:172-184 and :212
    MEASURED   2026-10-01, ContactOut /v1/stats phone_quota deltas: 10 and 8
               across two 15-profile calls
    STATE      REAL, and the remedy is UNKNOWN rather than TODO

`reveal_info` is the `contact_info` switch, and `contact_info` is **where the
email arrives**. False returns profiles with no address, which voids
verification and the canary with it. It is not a phone-only flag. An earlier
note in this project's own records said "set it to False for future
enrichments" - that is wrong and is retracted here.

The real fix would be an email-without-phone parameter on that endpoint. There
is no evidence in this repository that one exists. **UNKNOWN, not a task.**

## 3. The ledger's cost model is wrong in both directions

    CLAIM      enrich.COSTS neither over- nor under-states reliably; it is
               wrong by a factor that depends on company size
    AUTHORITY  ContactOut /v1/stats quota deltas vs the waterfall ledger
    MEASURED   2026-10-01, two domains
    STATE      small domain: ledger 10, provider ~5 units (over-charged)
               95-employee domain: ledger 10, provider 16 email + 30 search
               + 10 phone = 56 units (UNDER-charged, 5.6x)

Cause: `ASSUMED_PROFILES = 5`, and a well-staffed domain returns 15. The cap
therefore does not bind what it claims to bind. Also measured: ContactOut's
`count` / `search_count` / `phone_count` fields read 0 for up to 8 hours
(`src/costs.py:106`) - only the `quota` decrements answer, so any spend read
taken within minutes is PENDING_SETTLEMENT and not RECONCILED.

## 4. `merge_contacts` drops the field that admitted the contact

    CLAIM      a contact admitted by company-NAME match cannot be audited
               afterwards, because the deciding field is not stored
    AUTHORITY  src/enrich.py:607-610 - the `fresh` dict omits `company`
    MEASURED   2026-10-01 on a live record
    STATE      Six people were admitted to one record through
               `enrich.same_company`'s no-address company-NAME branch on an
               exact "big fish (R)" match - among them a Head Chef and an
               Entrepreneur Agricole, plainly not employees of a branding
               consultancy. Three classified as `economic_buyer`.

They were harmless only because they had no address. Re-asking
`same_company` on the STORED contact returns False for all six, so the record
cannot explain its own contents. The docstring's audit argument for `excluded`
applies to KEPT contacts too.

## 5. FREE_MAIL is a fall-through, and nothing downstream refuses an address

    CLAIM      a webmail address is admitted onto a record on a lowercase
               company-NAME match, and only the persona filter removed it
    AUTHORITY  enrich.FREE_MAIL / enrich.same_company / enrich.company_labels
    MEASURED   2026-10-01, reproduced on both paid domains
    STATE      icloud.com and hotmail.co.uk admitted on one record; a
               hotmail.co.uk `Owner` - a CANONICAL economic_buyer - admitted
               on the other. Both outcomes were correct and NEITHER was
               corrected by an address rule: the persona gate removed the
               first pair, and an instruction given to the agent removed the
               second. There is no gate that refuses a free-mail address for
               a company-domain prospect.

## 6. `?search=<domain>` is not a domain filter

    CLAIM      a dotted-domain probe at the provider returns unrelated rows
    AUTHORITY  src/collision.py search_term; measured live
    MEASURED   2026-10-01
    STATE      `?search=thirstcraft.com` returned 15 rows including one at
               `conexioncreative.com`; the bare label `thirstcraft` returned
               0 with meta.total 0. A dotted probe is uninformative in BOTH
               directions - it can invent history and it can hide it.
               Already documented in `collision.search_term`; recorded here
               because a control built on it misleads the person running it.

## 7. The touch ledger records 0 against 912 provider-confirmed sends

    CLAIM      local gates cannot see what our own paused campaigns sent
    AUTHORITY  work/queue.jsonl vs provider readback
    MEASURED   2026-10-01
    STATE      31 of 43 shortlisted people had already been mailed by OUR
               campaigns 491-498/503, and `eligibility.must_not_contact`
               passed every one of them, because the record carries no touch.
               Reconciling the ledger from provider truth is the fix.

## 8. Smaller, recorded so they are not rediscovered

    scripts/task_registry.py --status REWRITES docs/state/TASK-REGISTRY.json
      as a side effect of a read.
    tests/test_linkedin_lint.py has 3 pre-existing errors on master
      (`module 'src.personalization' has no attribute 'settings'`) - fixed by
      the 2026-10-01 restore, listed here in case they recur.
    src/eligibility.py's LinkedIn branch calls `_claim_detail(unsupported)`
      twice in one expression.
    docs/state/PROVIDER-CAMPAIGNS.json still carries the pre-tri-state
      ownership verdict; regenerating it would move an estimated 17 of 20
      campaigns to `unknown`.
    max_contacts_to_enrich = 1 per company caps verification to one contact,
      so other canonical contacts on a record are UNKNOWN rather than
      invalid. Fine for a canary, wrong for a cohort.
