# TASK-026 - What the copy that gets replies has in common

Operator backlog: QWEN-20, and item 8 of the analysis list.

## GOAL

A measured description of the subject and opening patterns that correlate
with replies in the client's own estate, and an honest statement of how
little that proves.

## WHY IT MATTERS

The best campaign in the estate replies at 12.23% and the worst multi-step one
at 1.44%. Their sequences are readable. Nobody has compared the WORDS against
the outcome, so every copy decision this system makes is made from first
principles against a client whose own history has an answer.

## WHERE THE DATA IS

Claude holds the provider credentials; this worktree has none, by design and
structurally - `config/.env` does not exist here. So the provider reads are
already done and the results are on disk OUTSIDE any repository:

    C:\Users\Zvonimir\Desktop\resonate-analysis\

    replies_email.jsonl      sanitised inbound email replies
    replies_linkedin.jsonl   sanitised inbound LinkedIn messages
    bison_campaigns.json     22 EmailBison campaigns with outcome counters
    hr_campaigns.json        83 HeyReach campaigns with progressStats

The reply bodies are SANITISED: emails, URLs, phone numbers and every personal
and company name this system knows are replaced with placeholders. They are
still real client correspondence. **Read them, never copy them.** No body, no
fragment of a body, and no name may enter this repository - not into a
fixture, not into a docstring, not into a commit message. Invent every example
you need. `tests/test_fixture_hygiene` is failing today because that rule was
broken before.

Do NOT attempt a provider call. There are no credentials here, and a task that
tries to get some has misunderstood its job.


## SCOPE

Work from `bison_campaigns.json` plus the sequence subjects, which Claude
exports to `resonate-analysis/bison_sequences.json`. Compare, per campaign and
against reply rate:

- subject length, and whether it is a question
- how many spintax variants each step carries
- whether `{COMPANY}` or `{FIRST_NAME}` appears in the subject
- `Re:` threading, and at which steps
- the CTA shape of the final steps - referral ask, breakup, meeting ask
- first-line opening pattern

Then the same for the LinkedIn side from `replies_linkedin.jsonl`, which
carries what prospects wrote BACK - the strongest available signal about which
messages landed, even though the outbound text is not joined to it.

## THE TRAP TO AVOID

Every high-performing campaign in this estate was built in the same rebuild,
so subject variants, sequence length and new copy are perfectly confounded. A
ranking of copy features that does not say this is a ranking of WHEN the
campaign was written. Say it in the report, in the first paragraph.

## FILES ALLOWED

`scripts/`, `docs/`, `docs/qwen-tasks/`, `tests/`.

## FILES FORBIDDEN

`src/**`, `work/**`. And no real reply body, name or company reaches this
repository - see WHERE THE DATA IS.

## TESTS REQUIRED

Tests on invented rows for every feature extractor. A subject parser that
mis-splits spintax would produce a confident wrong ranking.
