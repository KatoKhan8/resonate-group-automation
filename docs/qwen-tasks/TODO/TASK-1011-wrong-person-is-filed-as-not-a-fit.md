# TASK-1011 - "wrong person" is filed as "not a fit", and the named person is never activated

**Opened by lane 3, 2026-10-03**, classifying the 21 unmatched phase-2
firings. Full context: `docs/PHASE2-UNMATCHED-CLASSIFICATION-2026-10-03.md`,
section 2 rows 5-6 and section 5. Verdict: **pravi defekt**.

Number chosen by inspection, not by the task allocator - see TASK-1010.

---

## Part 1 - the classification error

### The defect

`\bwrong person\b` is a member of `NOT_RELEVANT_PATTERNS`, and `NOT_RELEVANT`
ranks above `REFERRAL` in `RULES`. So a reply that names the right person is
classified `not_relevant`, mapped to the outcome `not_icp`, and resolved
through `reply.on_negative` - which labels the account "Not a fit".

Two things are lost:

1. **The referred person is never activated.**
   `reply.activate_referred_contact` ("A referral is an explicit escalation:
   the referrer said 'talk to B', so B is activated") is reachable only from
   the `referral` outcome. On the `not_icp` path nothing activates anybody.
2. **The account is labelled as disqualified** rather than as redirected,
   which is the opposite reading of the same sentence.

### A second, related hole

`accountpolicy.OUTCOMES` contains `wrong_person`, and `OUTCOME_POLICY` maps
it to `reply.on_wrong_person` - ('continue', 'contact', "We wrote to the
wrong person", "Their colleagues may still be right. Only this sequence
stops."). That is exactly the right behaviour for this reply, **and no
classifier category maps to it.** Measured: `wrong_person` is unreachable
from `CLASSIFIER_OUTCOME`. A complete policy exists and nothing can ever
trigger it.

### Reproduction

On master `2bf7b8a5`, run from outside the `%TEMP%` root:

    py -3 -c "import sys; sys.path.insert(0, r'<repo>'); \
      from src import replies, accountpolicy; \
      v = replies.classify('wrong person, speak to our head of operations instead'); \
      print(v['classification'], v['evidence'], \
            accountpolicy.CLASSIFIER_OUTCOME[v['classification']])"

Observed:

    not_relevant ['wrong person'] not_icp

Expected: `referral` -> `referral`, or `wrong_person` if that policy is to be
the one used.

Note that `REFERRAL_PATTERNS` also matched this text (on `speak to`) - the
rule ordering, not a missing pattern, is what decides it.

### The fix, and the ordering argument it has to answer

`REFERRAL` is ranked LAST in `RULES` on purpose, and the reason is written
into the source: "`reply.on_referral` holds the replier where `on_negative`
and `on_wrong_person` stop them, so a referral winning over either of those
would leave somebody who refused merely paused - a classification softening a
stop." Any fix must not break that.

The contained fix is therefore **not** to re-rank `REFERRAL`. It is to move
`\bwrong person\b` out of `NOT_RELEVANT_PATTERNS`, where it does not belong:
"wrong person" says nothing about whether the company is a fit. Either

- **(a)** give it its own rule returning a category that maps to the
  `wrong_person` outcome, which makes the existing dead policy live; or
- **(b)** move the phrase into `REFERRAL_PATTERNS`.

(a) is preferred. It uses a policy already written and reviewed, it keeps
`REFERRAL` last so the softening argument is untouched, and
`reply.on_wrong_person` is `continue`-at-contact-scope, which is strictly
safer than referral's `stop`-plus-activate.

Acceptance: S13's two fields match; no row in the 899-reply corpus moves OUT
of a stop class; and the diff of corpus classifications is listed row by row.

---

## Part 2 - `channels` reads an unsubscribe but not a stop

Found while classifying S24 and S29. Those two scenarios are mis-specified
(they assert the wrong authority) but what they walked into is real.

`channels.email_verdict` / `channels.linkedin_verdict` read
`operator_excluded`, `unsubscribed`, `suppressed`, `no_address`, `bounced`,
MX, verification, `no_profile`, `linkedin_url_not_canonical`,
`duplicate_identity`. They do NOT read `contact["stopped"]` and they do NOT
read a reply event. Measured, with a control:

    negative reply on record    channels.linkedin_verdict = (True, None)
    contact['stopped']          channels.linkedin_verdict = (True, None)
    contact unsubscribed        channels.linkedin_verdict = (False, 'unsubscribed')

**No send escapes.** `eligibility.must_not_contact` returns
`blocked:replied` and `blocked:contact_stopped` respectively, `executionguard`
lists both, and `heyreachfactory` calls it (line 1225). This is a reporting
and ranking defect, not a sending one.

It still matters, because `channels` is documented in its own source as "the
canonical answer to which channels can this person be reached on ...
consulted by the preview, the reports and the coverage summary, none of which
go through `eligibility`", and some fifteen call sites take its answer -
`web/api.py` (the contactable/held view), `nextaction`, `priority`,
`contextpack`, `demo_outreach`, `simulator`. A person who refused is counted
as contactable in the operator's own view of the estate, and `priority` can
rank them.

### Proposed fix

Add two checks to both verdicts, beside `_unsubscribed` and with the same
shape, returning new reason constants (`replied`, `contact_stopped`). Both
are contact-level, so both close both channels, which is the behaviour
`eligibility` already has.

**Decide first whether this is wanted**, because it changes what the preview
and the coverage summary report, and a count that drops is going to need an
explanation. It is a smaller change than it looks - `_bounced` is the
precedent, and its docstring records that a bounce was likewise "read by no
gate at all" until 2026-09-13.

## Status

TODO. Not started. No code changed by lane 3.
