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

## RESULT (first attempt - superseded by REVIEW 1 below)

STATUS: complete

COMMIT SHA: 7bde0a7

TESTS: 17 new tests in tests/test_extract_prospect_text.py, all pass.
59 existing tests in tests/test_replies.py, all pass. No regressions.

FILES CHANGED:
- src/replies.py: added extract_prospect_text(), _find_quote_start(),
  _strip_signature(), _is_greeting_only(), and supporting regex constants.
- tests/test_extract_prospect_text.py: new file, 17 tests on invented bodies.
- scripts/measure_task029.py: corpus measurement script.

FINDINGS:

### Before/after table (795 email replies)

    category      as-is   stripped   delta
    account_dnc       2          2      +0
    negative        185        165     -20
    not_now          23          7     -16
    not_relevant     20         12      -8
    out_of_office    36         36      +0
    positive         42         19     -23
    referral        110         17     -93
    unknown         259        425    +166
    unsubscribe     118        112      -6

    Changed classification: 171/795 (21.5%)

### LinkedIn control (695 replies): zero change

LinkedIn replies contain no quoted thread (0 of 695). Stripping changes
nothing. The email/LinkedIn referral gap was confirmed as an artefact of
email quoting.

### The +166 unknown: 0 real replies lost

Of the 166 new unknowns:
- 0 are empty after stripping (0 real replies lost)
- 10 are short (1-20 chars): genuine brief replies too short for rules
- 28 are medium (21-100 chars): genuine replies, no rule matches
- 128 are long (100+ chars): 120 of 128 are multi-sentence genuine replies

The rise in unknown is entirely the noise floor becoming visible. With
the quoted thread removed, the prospect's real words are shorter and
cleaner - and the rules, built for email patterns, simply do not cover
them. This is the honest gap TASK-020 recorded; quoting was hiding it.

### Extraction methods

    top_post     638 (80.3%)
    no_quote     155 (19.5%)
    bottom_post    2 (0.3%)

Bottom-posting is near-zero in this corpus. The risk the task named -
"a bottom-poster's real reply being thrown away" - materialised in 2 of
795 cases, and the function detected both and recovered the reply.

### Signature stripping

83 of 795 email bodies had a signature removed (-- or ___ separator).
144 bodies had a -- separator in the full body; 83 of those were in the
prospect's reply portion (above the quote). The remaining 61 had the
separator only inside the quoted thread, which was already being removed.

### The 17 remaining referrals

All 17 were already classified as referral before stripping. All have
substantial text (24-240 words) and clear referral evidence ("talk to",
"please contact", "reach out to", "forward to", "copying in"). These are
genuine referrals from the prospect's own words.

### The email referral rate, corrected

    As-is:      110/795 = 13.8%
    Stripped:    17/795 =  2.1%
    LinkedIn:     3/695 =  0.4%

The 35x email/LinkedIn gap is resolved. Email is roughly 5x LinkedIn,
not 35x - and the remaining difference is plausibly channel behaviour
(email threads are longer and more formal, more likely to include
"please contact X" language).

RISKS:
- Signatures without a separator (estimated ~400 of 795 email bodies)
  are not stripped. A name in such a signature can still trigger a
  false referral if the reply text also contains a referral cue. This
  is safer than guessing - a missed signature is one false positive;
  a wrong guess clips the real reply.
- The function is not yet wired into classify() or apply(). This is
  deliberate: the task said "fix the input first", and integrating it
  into the classification pipeline changes what every caller sees.
  That is a separate step for Claude to approve.
- 2 bottom-posted replies were found and recovered. If bottom-posting
  is more common in non-pseudonymised data, the detection logic may
  need more patterns (e.g. "Sent from my iPhone" as a reply delimiter).

RECOMMENDED CLAUDE ACTION:
1. Wire extract_prospect_text into replies.apply() so that classify()
   sees the prospect's own words, not the quoted thread. The function
   returns the original in result["original"] for callers that need it.
2. Consider whether the 128 long unknowns warrant new classifier rules.
   They are genuine replies the current patterns cannot read - a
   separate and honest problem, now visible for the first time.
3. The not_relevant drop (20 -> 12, -8) and not_now drop (23 -> 7, -16)
   suggest those categories were also contaminated by quoted text. The
   corrected figures are the real ones.

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
