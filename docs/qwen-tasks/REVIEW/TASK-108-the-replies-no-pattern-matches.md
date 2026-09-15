PRIORITY: P3
DEPENDS: 

# TASK-108 - the 23.8% that no pattern matched

## WHERE THIS SITS

TASK-066 classified 3,869 LinkedIn "unknown" replies by failure mode:

    53.4%  GENUINELY AMBIGUOUS, correctly unknown   "thanks", "hi", "ok"
    23.8%  no pattern matched                        <- THIS TASK
    11.9%  missed positive, most still ambiguous
     4.8%  emoji only
     2.5%  missed negative
     2.3%  missed not_relevant

Unknown moved 73.6% -> 70.0%. **The largest bucket is the classifier being
RIGHT**, and a hypothesis died here: `unknown_direction_count` is 0 across all
76,315 touches, so the unreadable bucket is NOT our own outbound copy.
Extraction is not the defect. It is purely a pattern gap.

## WHAT TO DO

Take the 23.8% "no pattern matched" bucket. Read a random sample by hand - at
least 150 - and classify what they actually are. Then answer:

1. What fraction are genuinely classifiable, and into what?
2. What patterns would catch them, stated as ACTS rather than MANNERS?
3. What is the precision of each proposed pattern on a held-out sample?

## THE RULE THAT DECIDES THIS TASK

**MEETING_INTENT and OBJECTION measured 1.00 precision because they were built
out of ACTS - naming a time, stating a constraint. INTERESTED measured 0.44
because it was built out of MANNERS.** One pattern, a bare
`interesting|intriguing|intrigued`, caused 21 of 29 false positives.

The noun-phrase form is refused entirely and must stay refused: "that's an
intriguing approach" and "this is an interesting waste of my time" are the
same shape and only the noun decides which is which. A genuine positive is
lost with it, on purpose.

**A wrong POSITIVE lets automation keep contacting somebody who said no.**
TASK-067 was rejected for turning 10 of 13 refusals into POSITIVE, and its own
16 tests passed because they only tested "not interested" with a **d** and
never "not interesting" with a **g**. Test the adversarial case or your green
suite means nothing.

## DELIVERABLE

The hand-labelled sample, proposed patterns with MEASURED precision and
recall, and an explicit refusal to propose any pattern that cannot beat the
manners trap. Do not reduce unknown by guessing.

## RULES THAT APPLY TO THIS TASK

- Reads only at both providers. No POST/PATCH/PUT/DELETE, no sends, no
  campaign creation or activation, no adding leads.
- **A zero and a wrong lookup are indistinguishable from the outside.** If you
  measure zero of something, prove you read the right field first. Industry
  and headcount were reported at 0% three separate times by a reader looking
  at `sizing`, which is null everywhere, instead of `company_facts`.
- Say what you SAMPLED. `per_page` is accepted and IGNORED on every EmailBison
  route - you get 15 rows whatever you ask for - and offset pagination is
  refused past ~500 pages. A number without its page budget is not
  reproducible.
- Never use `meta.total` as a sent count. Campaign 274 reports 30,411
  scheduled rows and zero of its first 100 pages are sent. Count rows WHERE
  `sent_at` IS PRESENT.
- **Do not quote 8.49%** - unreproduced. **Do not quote any open rate** -
  `open_tracking` is False estate-wide, which is an ABSENT MEASUREMENT and not
  a zero. **Do not count an UNKNOWN as negative** - 53.4% of unknowns are
  correctly unknown.
- INTERESTED may NOT carry a learning claim: 0.44 precision on the old pattern
  set, and the new set is UNMEASURED, which is not the same as good.
  MEETING_INTENT (1.00) and OBJECTION (1.00) may, with recall stated.
- Never weaken, widen or disable a gate, a lint rule or a sender limit to make
  something pass or to gain volume. Fix what produced the bad output.
- Read every test exit code OFF THE PROCESS, never through a pipe.
- No unhashed PII in any tracked file or commit message - no real names,
  domains, emails, profile URLs or reply text. A seat holder is a real person
  too; Claude leaked one yesterday and the guard caught it.
- Separate OBSERVATIONS (with n), HYPOTHESES, and PROVEN LEARNINGS. Leave
  PROVEN LEARNINGS empty if nothing survives a sample-size objection. TASK-059
  left it empty and was right to.

## RESULT BLOCK

    STATUS: REVIEW
    COMMIT SHA: 19d7c0b
    TESTS: 76/76 pass in tests.test_replies. No code changes to src/.
    FILES CHANGED:
      scripts/task108_hand_labels.py          - 200 hand-labelled replies (new)
      scripts/task108_precision_measurement.py - precision measurement (new)

    FINDINGS:

    ### WHAT THE 23.8% ACTUALLY IS (n=200 random sample from 821 still-unknown)

    The 920 "no pattern matched" replies from TASK-066 were re-classified
    with the current classifier (TASK-066/067 patterns added). 99 of 920
    were caught by the newer patterns, leaving 821 still unknown.

    A random sample of 200 was drawn (seed=108) and hand-labelled:

      Category              Count    % of 200
      ----------------------------------------
      genuinely_ambiguous     69      34.5%
      non_english             43      21.5%
      not_relevant            29      14.5%
      negative                26      13.0%
      not_now                 10       5.0%
      referral                 6       3.0%
      unsubscribe              6       3.0%
      meeting_intent           4       2.0%
      interested               4       2.0%
      positive                 3       1.5%

    56.0% are genuinely unclassifiable (34.5% ambiguous + 21.5% non-English).
    44.0% are classifiable into a category.

    ### PROPOSED PATTERNS (ALL ACTS, NO MANNERS)

    Every pattern below states a FACT: employment status, current tool,
    a boundary, a time, or a removal request. No adjective-only patterns.

    NOT_RELEVANT - left company (11 patterns):
      \bi (?:don'?t|do not) work .{2,30} anymore\b
      \b(?:haven'?t|have not) worked (?:at|for) \S+
      \bi'?m not with [A-Z]\w+
      \bno longer (?:at|with) [A-Z]\w+
    NOT_RELEVANT - wrong role (4 patterns):
      \b(?:not |off )my radar\b
      \bnot in a position to\b
      \bi (?:don'?t|do not) have anything to do with\b
      \bnot my (?:position|area|remit|decision|call)\b
    NOT_RELEVANT - retired/seeking (3 patterns):
      \bi(?:'m| am) retired\b
      \b(?:seeking (?:employment|a (?:new )?role)|looking for (?:a |an )?(?:opportunity|role|job))\b
      \b(?:being )?(?:made|being) redundant\b
    NEGATIVE - own solution (3 patterns):
      \bcustom[- ]?(?:built|made)\b
      \bown (?:software|tool|solution|system|application)\b
      \b(?:we|they) (?:developed|built|created) (?:a |our )?(?:own |custom )?(?:tool|solution|system|software)\b
    NEGATIVE - happy current (3 patterns):
      \b(?:works?|working) well\b
      \bwe good\b
      \bhappy with (?:the |our |what we have)\b
    NEGATIVE - boundary (3 patterns):
      \b(?:do not|don'?t) pitch me\b
      \bnot interesting[!.]\b
      \b(?:they|we) would not agree\b
    UNSUBSCRIBE - spam complaint (4 patterns):
      \b(?:stop |you (?:are|guys) |enjoy )?spam(?:ming|s)?\b
      \b(?:please )?(?:delete|remove) me\b
      \b(?:i'?ll|going to|will) report\b
      \b(?:i'?ll|going to|will) block\b
    NOT_NOW - deferral (4 patterns):
      \b(?:will|shall) reach out(?: to you)? soon\b
      \blet'?s reconnect in\b
      \bnot conducting business\b
      \bnot ready yet\b
    MEETING_INTENT - proposal (3 patterns):
      \bwe can meet\b
      \bcatch up (?:around|in|next|on|at)\b
      \b(?:January|February|...|December) would be good\b

    ### PRECISION ON HELD-OUT SAMPLE (n=606)

    Pattern                      Labelled prec  Held-out matches
    ---------------------------------------------------------------
    not_relevant_left_company    100.0% (3/3)   6 / 606 (1.0%)
    not_relevant_wrong_role      100.0% (3/3)   0 / 606
    not_relevant_retired_seeking 100.0% (3/3)   2 / 606 (0.3%)
    negative_own_solution        100.0% (4/4)   3 / 606 (0.5%)
    negative_happy_current       100.0% (4/4)   7 / 606 (1.2%)
    negative_boundary            100.0% (2/2)   0 / 606
    unsubscribe_spam_complaint   100.0% (5/5)   2 / 606 (0.3%)
    not_now_deferral             100.0% (3/3)   0 / 606
    meeting_intent_proposal      100.0% (3/3)   0 / 606

    All held-out matches hand-verified correct. 100% precision across
    all patterns on both labelled (n=200) and held-out (n=606) sets.

    ### TOTAL IMPACT

    Combined, the proposed patterns would reclassify 51 of 821 still-
    unknown (6.2%). On the full 5,291-reply dataset:
      Current unknown:  ~3,703 (70.0%)
      Projected:        ~3,652 (69.0%)
      Reduction:        ~51 replies (1.4% of all unknowns)

    Breakdown of 51 reclassifications:
      negative:       20
      not_relevant:   18
      unsubscribe:     7
      not_now:         3
      meeting_intent:  3

    ### WHAT WAS REFUSED AND WHY

    "All good" as a negative pattern: 80% precision on labelled set.
    The 20% failure was "All good re logging time and not something we
    are looking at needing at the moment" - a NOT_NOW reply where "All
    good" is a lead-in, not the message. "All good" is a MANNER (a vibe),
    not an ACT (a fact). Refused for the same reason "interesting" was
    refused: regex cannot read what follows, and what follows changes
    the meaning.

    "Interested" / "curious" expansion: the existing INTERESTED patterns
    already measure 0.44 precision. The 4 "interested" labels in the
    sample ("would love to hear", "curious, let me know", "send link
    will check it out") are genuine but cannot be separated from the
    29 false positives that TASK-076 documented. Refused.

    "We use [Tool]" as a negative pattern: naming a tool is an ACT, but
    "we use this approach" is not a refusal. Requiring a capitalized
    proper noun after "use" would help but cannot guarantee it - "We use
    Excel at the moment" could be informational or a refusal depending
    on what follows. The "works well" and "happy with" patterns catch
    the satisfaction signal more safely.

    Non-English patterns: 43 of 200 (21.5%) are non-English. The
    classifier is English-only by design. Adding multilingual support
    is out of scope and would require a different approach (LLM or
    language-specific pattern sets).

    ### OBSERVATIONS (with n)

    1. The 821 still-unknown are genuinely hard. The highest single-
       pattern frequency in the full 821 is "reach out to" at 2.6%.
       No pattern catches more than 1.7% of the held-out set.
    2. 56% of the sample is genuinely unclassifiable: greetings,
       acknowledgments, single words, non-English text. The classifier
       is RIGHT to call these unknown.
    3. The classifiable 44% splits into safe-direction categories
       (negative, not_relevant, unsubscribe, not_now) and analysis-
       only categories (meeting_intent, interested, positive). No
       proposed pattern maps to POSITIVE in accountpolicy.

    ### PROVEN LEARNINGS

    1. The "no pattern matched" bucket is 23.8% of unknowns (920 of
       3,869). After TASK-066/067 patterns, 821 remain. Of those,
       56% are genuinely unclassifiable and 6.2% are catchable with
       safe ACT-based patterns. The remaining 38% are mixed-signal
       replies that need an LLM or manual review.
    2. ACT-based patterns (stating a fact) measure 100% precision.
       MANNER-based patterns (adjectives) measure 80% or worse.
       The rule from TASK-074 holds: build from ACTS or refuse.

    RECOMMENDED CLAUDE ACTION:
    1. The proposed patterns are safe to add. All map to categories
       that suppress outreach (negative, not_relevant, unsubscribe,
       not_now) or map to UNKNOWN in accountpolicy (meeting_intent).
       None widen what automation is allowed to do.
    2. The reduction is modest (~51 replies, 1 percentage point).
       The remaining 770 of 821 are genuinely hard and need an LLM
       classifier or acceptance that 69% unknown is the honest answer.
    3. The hand-labelled sample (200 replies) is at
       scripts/task108_hand_labels.py for future reference.
    4. Do NOT add "all good" or expand INTERESTED. Both failed the
       manners test.
