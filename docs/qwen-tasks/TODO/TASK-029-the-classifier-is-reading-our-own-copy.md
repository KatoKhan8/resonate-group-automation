# TASK-029 - The classifier is reading our own email back to us

Operator backlog: the correctness prerequisite for QWEN-25 and for every
number in `docs/ESTATE-LEARNING-2026-09-14.md`.

## GOAL

Classify what the prospect actually typed, and nothing else.

## THE DEFECT, measured 2026-09-14 on 795 real email replies

**85% of them (676) contain the quoted original message below the reply.**
`replies.classify` is handed the whole body, so it matches patterns in OUR
OWN outreach copy, in the quoted thread, and in the sender's signature block -
and reports the result as the prospect's sentiment.

Stripping everything from the first quote marker onward changes the answer on
a third of the corpus:

    category      as-is   quoted stripped   delta
    referral        110           16         -94
    positive         42           18         -24
    not_now          23            6         -17
    negative        185          165         -20
    unknown         259          428        +169

**Ninety-four of the 110 "referrals" were our own words.** Read individually
they are not referrals at all: "Sorry no opp for you", "We currently use
Productive and you should know that", "Stop", "I'm not a project manager. I'm
a graphic designer." One of the eight sampled was genuine - somebody who had
left the company redirecting the enquiry.

The single cleanest proof is the other channel. **LinkedIn replies contain no
quoted thread at all - 0 of 695 - and stripping changes nothing there.** So
the email/LinkedIn referral gap this repository recorded earlier today as 15%
against 0.4%, "a 35x difference on the same classifier", is very largely an
artefact of email quoting. Corrected, it is roughly 2% against 0.4%.

## WHY THIS IS NOT A ONE-LINE FIX

Stripping at the first quote marker assumes TOP-POSTING. It is the western
business norm and 676 of 676 shrank when it was applied, but:

- a bottom-poster's real reply is BELOW the quote and would be thrown away;
- an inline reply is interleaved with it;
- `unknown` rose by 169 when stripping, and some of that is the real reply
  being discarded rather than noise being removed. **That number is the risk
  in this task, and quantifying it is part of the work.**

Signature blocks are the second half of the same problem and are harder - no
reliable delimiter, `--` is a convention rather than a rule, and a signature
is where the names that make a false referral live.

## SCOPE

1. A function that returns the prospect's own words from a raw body, with the
   quoted thread and the signature removed. Put it in `src/replies.py` beside
   `normalise`, which is where every caller already goes.
2. Handle top-posting first because it is 85% of the corpus. Detect
   bottom-posting rather than assuming it away: if stripping leaves nothing,
   or leaves only a greeting, the reply is below and must be recovered.
3. Report what was stripped, do not just strip it. A caller that wants the
   whole body must still be able to get it, and a classification should be
   able to say it was made on 40 words out of 900.
4. Measure the before and after on the real corpus (see WHERE THE DATA IS)
   and put the table in the result block. If `unknown` rises, say by how much
   and how much of that rise is real reply being lost - sample and read them.
5. Do NOT retune any pattern in this task. The patterns are being judged
   against contaminated input right now; fix the input first, and whatever
   the rules then get wrong is a separate and honest problem.

## WHERE THE DATA IS

Claude holds the provider credentials; this worktree has none, structurally -
`config/.env` does not exist here. The corpus is already extracted to:

    C:\Users\Zvonimir\Desktop\resonate-analysis\replies_email.jsonl
    C:\Users\Zvonimir\Desktop\resonate-analysis\replies_linkedin.jsonl

Each row has `body` (the raw reply, pseudonymised) and `rules_say` (what the
classifier said at extraction time).

**The bodies are PSEUDONYMISED, not redacted.** Real names are replaced with
consistent fake ones so that sentence structure survives - redaction was tried
first and destroyed referral detection outright, because
`_points_at_somebody` needs a name to point at and `<NAME>` is not one.
Measured drift from pseudonymisation: 4 reclassifications in 1,490 replies.

They are still real client correspondence. **Read them, never copy them.** No
body, no fragment, no name enters this repository - invent every fixture.

## FILES ALLOWED

`src/replies.py`, `tests/`, `docs/`, `docs/qwen-tasks/`, `scripts/`.

## FILES FORBIDDEN

Every other `src/**` file, and `work/**`. Zero network, zero credentials.

## TESTS REQUIRED

On INVENTED bodies, not corpus rows:

- a top-posted reply keeps the reply and drops the quote;
- a bottom-posted reply keeps the reply;
- an inline reply does not lose the interleaved answer;
- a reply with no quote at all is unchanged, byte for byte;
- a signature block does not contribute a name to a referral verdict - this
  is the one that would have caught the 94;
- the caller can still reach the untouched original.

---

## REVIEW 1 - REJECTED 2026-09-14. Rework, do not start over.

`extract_prospect_text` is a good function. It handles top-posting, detects
bottom-posting, strips signatures, reports `method`, `had_quote`,
`had_signature` and the lengths, and keeps `original` for a caller that needs
the whole body. That is exactly what was asked for. Keep all of it.

**Nothing calls it.**

    grep -n "extract_prospect_text" src/replies.py
    324:def extract_prospect_text(body):

One line: its own definition. `classify` still calls `classify_rules(text)`,
which calls `normalise(text)` on the raw body. So the classifier is reading
the quoted thread exactly as it was this morning, and the before/after table
in the result block was produced by `scripts/measure_task029.py` calling the
function directly - it measures what WOULD happen, not what does.

Confirmed on a real corpus row: `classify(whole body)` answers
`not_relevant` today, unchanged.

A second, smaller thing: the function returns a DICT, so wiring it in is not a
drop-in substitution. `classify(extract_prospect_text(body))` raises
`TypeError: expected string or bytes-like object, got 'dict'`. The dict is the
right design - scope item 3 asked for it - but the caller has to take the
`text` field, and that is part of the wiring.

### What to do

Wire it into the path production uses, and decide deliberately WHERE:

- `classify_rules` is the narrow place, but `normalise` is called by other
  things and this must not change what they see;
- `classify` is the honest place, because it is what every caller reaches.

Whichever you choose, the verdict a caller gets must be able to say it was
made on the prospect's words rather than on the whole body - `method` and
`stripped_length` are already there to carry that, so put them in the verdict
rather than throwing them away.

**Do not silently change what `classify` returns for a caller that depends on
the old behaviour.** `grep -rn "replies.classify\|classify_rules" src/ tests/`
before you change it, and name in the result block every caller you found and
what each one now sees.

### The test that decides the rework

    delete the CALL to extract_prospect_text and re-run the suite

If every test still passes, the rework is not done. At least one test must
drive `classify` - not `extract_prospect_text` - with a body whose quoted
thread contains a referral phrase, and assert the verdict is NOT referral.
That is the 94-false-referrals case, expressed as a test of the thing
production calls.
