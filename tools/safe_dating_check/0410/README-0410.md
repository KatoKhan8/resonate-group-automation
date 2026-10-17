# webapp/0410 — the comma-split-quote census, and a ladder that selects rather than picks

This directory sits on top of `tools/safe_dating_check/` (webapp/0400,
`ded7a4a91`). It does not modify the instrument: `safe_dating.py`,
`run_arms.py` and `step6_corrections.py` are the committed bytes and are
imported, never edited. Everything here is a layer around them.

## What is in here

    census_q.py      applies src/contested.py's OWN predicate
                     `entry["now"].split(",")[0]` to RECOMMENDATIONS exec'd out
                     of every commit's blob.  Output: the predicate's output
                     set Q, per commit, with each blob's sha/size/CR printed.
    classify.py      imports step6_corrections.PUBLISHED (the lane's 10
                     published datings) and partitions them against Q into
                     five classes, A..E.  Nothing is retyped: the needles come
                     out of the persisted module, Q comes out of the blobs.
    redate.py        re-dates a row through the unmodified precheck and
                     parent-count rule, with a disambiguation ladder and the
                     SUBJECT-IDENTITY check.
    plant_control.py the uniqueness rule fired on a PLANTED ambiguous needle in
                     a synthetic repo, with the unique and absent arms beside
                     it.  Builds and removes its own fixture.
    reference/       the known-answer outputs of the two runs above.

Run everything with `py -3 -B`. Redirect stdout through a UTF-8 wrapper —
these scripts print `repr()` of needles containing non-ASCII punctuation and
the Windows console codepage will raise on them.

## THE DEFECT THIS DIRECTORY EXISTS TO NOT REPEAT

0390 recorded: *"the ladder's `winner` is a necessary condition for a verdict,
never a sufficient one — the next task will be tempted to read
`ladder_winners.json` as the answer."*

The first version of `redate.py` was tempted in a way 0390 did not predict. It
did not read a stored winner; it **chose** one — the first candidate in
document order whose count was 1 — and then ran the subject-identity check on
that choice. For `64 files, not 2,502` the first unique candidate is
`#   64 files, not 2,502` at line 832, which is a **comment**. Subject-identity
correctly failed, and the row came back `PERMANENTLY-AMBIGUOUS` when the right
answer is `UNCHANGED` at `f55fc043a`. A driver that picks one candidate and
then tests it is testing its own choice, not the question.

**The repair is not to relax subject-identity. It is to stop choosing.** Every
candidate is scored; subject-identity *selects* among the unique ones; and if
more than one survives they must all date identically or the row is refused.
That last clause is `NEEDLE-CHOICE-INDEPENDENCE` and it is printed on every
row: 3 subject-identical needles for row 8, 1 distinct answer; 2 for row 9 at
the alternate reference, 1 distinct answer.

It was caught by the brief's known-answer control and by nothing else. A
re-dating run without a known-answer row would have shipped the wrong verdict.

## The verdict grammar, and why one verdict is protocol-dependent

    UNCHANGED              a subject-identical unique needle exists, every such
                           needle gives one CONFIRMED-INTRODUCTION, and it
                           equals the published figure
    MOVED                  same, and it does NOT equal the published figure
    REFUSED-BY-PRECHECK    the bare needle is AMBIGUOUS-NEEDLE or
                           NEEDLE-ABSENT-AT-REF and NO LADDER IS ATTEMPTED
    PERMANENTLY-AMBIGUOUS  a ladder was attempted and no unique candidate names
                           the subject — including the case where the subject
                           does not exist at the reference blob at all

`REFUSED-BY-PRECHECK` and `PERMANENTLY-AMBIGUOUS` are **the same measurement
under two protocols**, not two findings. Say which protocol you ran, or the
partition is not interpretable.
