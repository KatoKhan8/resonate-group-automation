#!/usr/bin/env python3
"""What a stageable fixture record carries since 2026-09-25: its own
research, and an opener grounded in it.

    from tests import packfixture

    rec["research"] = [packfixture.own_fact(rid, domain, company)]
    step["body"] = packfixture.opener(first, company)

## WHY THIS EXISTS

`bisonfactory.stage` runs `copylint.check_batch` before the first provider
call of any kind, and `copylint`'s first rule is that step 1 opens on a line
this account's own research supports. A lead with no pack is not quietly
excused - it fires the rule. That is the contract lane D merged on
2026-09-25, and it is right: measured the same day, 0 of the 636 production
leads carrying rendered copy had a single identity-checked pack fact.

Every staging fixture in this suite staged copy with no research behind it,
so every one of them modelled a push the product now refuses. Nine test
modules had to carry what a real push carries. They carry it from here rather
than each writing its own, for one concrete reason: the fact and the opener
have to AGREE - the opener's words must appear in the fact, or rule 1 fires -
and nine independently hand-written pairs is nine chances for them to drift
apart, each discovered as a staging failure that looks like a product bug.

## AND WHY IT IS NOT ENOUGH TO HAND EVERY FIXTURE A PACK

If every fixture carries one, nothing in the suite can observe the lint
REFUSING, which is the same defect as a guard that cannot fire. Lane B hit it
an hour earlier with the cadence guard and answered it the same way:
`test_staging_a_campaign_twice_builds_one` keeps a dedicated test that strips
the pack off and asserts, BY EFFECT, that no campaign and no lead reached the
provider. `tests/test_the_copy_lint_refuses_the_real_send_path.py` is the
other half, and `foreign_fact` below is what it means by identity: the same
words, on somebody else's site.

## NOTHING HERE IS A REAL COMPANY OR A REAL PERSON

The domains a caller passes are reserved test domains, and the sentence is
invented. `tests/test_campaign_audit.py` asserts that no fixture carries real
people; this file must stay inside that.
"""

#: THE ONE SENTENCE. Both halves are built from it, so they cannot drift.
#:
#: Chosen against the lint's other five rules rather than for its prose. It
#: carries no figure, no date, no quoted phrase and no capitalised pair, so
#: `untraceable_company_claim` has nothing to extract; it contains no banned
#: phrase and no word in `copylint.BUZZWORDS`; and it has no spaced hyphen.
#: A fixture whose GROUNDING tripped one of those would refuse for a reason
#: nobody was testing.
GROUNDING = "runs delivery scheduling for independent clinics"

#: The account whose site the foreign fact was actually read from. A
#: reserved TLD, and deliberately not any domain a caller passes in.
ELSEWHERE = "southgale.test"


def own_fact(record_id, domain, company):
    """One research row that `packfacts` ADMITS for this record.

    It states no website of its own, so `packfacts.identity_of` falls back to
    the host of the page it was read from - which is the right test for a
    site crawl and the shape the estate's 394 crawled records already hold.
    `record_id` is stamped because `pack_for` refuses a row stamped for a
    different record, and a fixture that omitted it would be admitted for the
    weaker of the two reasons.
    """
    return {"fact": "%s %s." % (company, GROUNDING),
            "source_url": "https://%s/about" % str(domain).strip().lower(),
            "source_type": "local_http",
            "record_id": record_id}


def foreign_fact(record_id, company):
    """The same words, read off somebody else's site.

    Presence-wise a record carrying this has research; identity-wise it has
    none, and `packfacts` returns UNVERIFIABLE rather than admitting it.
    Measured 2026-09-24: 50 of the 71 job rows the research pilot returned
    belonged to a different company, which is the defect this models.
    """
    return dict(own_fact(record_id, ELSEWHERE, company), record_id=record_id)


def opener(first, company):
    """A step-1 body whose FIRST LINE leans on `own_fact`'s words.

    The grounding is on the first line and not under a greeting, because
    `copylint.first_line` takes the first non-empty line of step 1 and asks
    whether anything in it appears in the pack. A fixture that opened with
    "Hi Ada," would carry no word longer than four characters there and would
    fire the rule with a perfectly good pack sitting behind it.

    `first` and `company` both appear, so two leads in one batch differ -
    `duplicate_first_line` is a real rule and two fixture leads sharing one
    body is the real defect it found.
    """
    return ("%s, your site says %s %s.\n\n"
            "Most teams that size only see project margin once a project has "
            "closed, which is after the point where anything could be done "
            "about it.\n\n"
            "Is that roughly how it works for you today?"
            % (first, company, GROUNDING))


def html_opener(first, company):
    """`opener`, wrapped the way a fixture that stores HTML bodies stores it."""
    return "<p>%s</p>" % opener(first, company)
