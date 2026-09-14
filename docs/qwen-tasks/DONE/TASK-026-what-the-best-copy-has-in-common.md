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


## RESULT

STATUS: done

COMMIT SHA: 463f74c

TESTS: 35 tests in tests/test_copy_feature_extractors.py, all passing.
  Covers spintax parsing (8 tests), subject features (8 tests), CTA
  classification (4 tests), reply sentiment (5 tests), sequence feature
  extraction (4 tests), and mis-split guards (4 tests). All on invented
  fixtures. Run: `py -m unittest tests.test_copy_feature_extractors -v`

FILES CHANGED:
  scripts/analyze_copy_features.py (new) - feature extractors and analysis
  tests/test_copy_feature_extractors.py (new) - 35 tests on invented data
  docs/task026-copy-analysis-report.md (new) - the report

FINDINGS:
  1. Gen2 campaigns (Apr 22 rebuild, 7 campaigns, 113K sent) outperform
     gen1 (Apr 4, 5 campaigns, 3K sent) by 1.7x (1.42% vs 0.85%). But
     every copy feature changed simultaneously: spintax variants 1.5→3.0,
     Re: threading introduced, {FIRST_NAME} removed from subjects, questions
     removed, sequence length changed. The confound is total.
  2. The one finding that survives the confound: 8 steps outperforms 22 and
     35 within the same gen2 template. 22-step campaigns return 0.28-0.45%
     vs 1.16-2.36% for 8-step campaigns using the same sequence.
  3. Campaign 262 at 3.81% is the highest rate but on only 525 sends - not
     reliable. It uses the gen1 sequence.
  4. LinkedIn replies (695): 11.8% positive, 23.2% negative, 15.4% question.
     No outbound text is joined, so this is a floor on engagement, not a
     feature ranking.
  5. Email reply classifier does not handle French, Dutch or German replies
     (campaigns 329, 330, 331) - "unclassified_by_rules" is a language gap.
  6. Caller check: `grep -rn "analyze_copy_features" scripts/ docs/` returns
     the script itself and the report. The extractors are consumed by the
     analysis pipeline in main() and by the test suite. The report cites
     the measured numbers they produce.

RISKS:
  - The report's generation labels (gen1_apr4, gen2_apr22) are inferred from
    campaign names and IDs, not from a build log. If campaigns were edited
    after creation, the generation assignment could be wrong.
  - The spintax parser counts top-level variants only. A campaign that nests
    spintax differently would get a different count than what EmailBison
    actually renders. No ground truth on rendered variants is available.
  - The LinkedIn reply sentiment classifier is keyword-based and coarse.
    The 49% "other" bucket is honest but limits what can be said.

RECOMMENDED CLAUDE ACTION:
  The report is at docs/task026-copy-analysis-report.md. The one durable
  finding is that 8 steps beats 22+ within the same template. The copy
  feature correlations are real but uninterpretable due to the total
  confound. If Claude wants to disentangle features, the only path is a
  new campaign that varies one feature at a time against the same list
  and send window. The extractors in scripts/analyze_copy_features.py are
  available for that analysis when the data exists.
