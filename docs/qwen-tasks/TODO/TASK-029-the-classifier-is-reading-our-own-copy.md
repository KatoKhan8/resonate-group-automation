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
