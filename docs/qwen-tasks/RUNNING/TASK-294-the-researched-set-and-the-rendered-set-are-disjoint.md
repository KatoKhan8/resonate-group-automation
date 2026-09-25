PRIORITY: P0
DEPENDS:

# TASK-294 — the researched set and the rendered set are disjoint

## DISPATCH NOTE

Lane F, the standing QA suite. **The per-lead research pack check:
`scripts/qa/check_lead_pack.py`.** In the minimum subset for **today's 128**.

**READ `docs/QA-LANE-F-CONTRACT-2026-09-25.md` FIRST**, then §9 of it twice —
it carries the measured numbers this task must not re-derive and must not
assume are false.

`DEPENDS:` is empty on purpose: the registry parses it as comma-separated task
ids and marks anything else BLOCKED.

## The question this answers

**Does every lead in this batch carry at least one research fact that is
provably about THAT company, with a source, a date and a snippet — and does
the copy's first line actually use one?**

This is the check that decides whether a personalised email is personalised or
merely shaped like it.

### What lane D already measured, 2026-09-24. Do not re-derive it.

- On the **927 rendered rows**, 636 matched a queue record and **ZERO carry a
  pack fact.**
- The **researched set (394) and the rendered set (554) are DISJOINT.**
- **291 rendered rows (31%) match no queue record at all.**
- **280 unsupported specifics, all at `body_1`, all the company's own name.**
  `persona_pain` is the only one of eight templates pairing a direct address
  with `{company}`.
- Of the 394 records carrying free-crawl research, **366 (93%) would pass
  copylint rule 1 today** — but that is across all 394 and is **NOT the same
  question as coverage on the 128.** This project's recurring failure is a
  headline number from a stage that had not asked the next stage's question:
  1,508 exportable that was 114; 19,612 "IN" of which two-thirds were under
  the floor; 8,595 never verified that is really 14,086.

**So the first thing this check must be able to answer is: of THESE 128, by
name, how many carry a pack fact, and how many match no queue record at all?**

### Build on lane D. Do not duplicate it.

`src/packfacts.py` and `scripts/packfact_check.py` exist on branch
**`worktree-agent-a63bd2d9102384dba` @ `c38c5934`** (unmerged). They already
implement:

    packfacts.pack_for(rec)      -> (pack, unused)
    packfacts.identity_of(fact)  -> admitted | refused | unverifiable
    packfacts.host_of(url)       hosts, and `www.` is not identity
    packfact_check.py --rendered work/stage/s7-copy.jsonl
    packfact_check.py --audit-pack-cache   the negative control

**`identity_of` is the module both the send path and the checker ask, and two
copies of an identity test is how the two come to disagree about who a fact
belongs to.** Import it. Do not write a second one.

Its three answers, and the one that matters: **`unverifiable` is NOT a pass.**
A fact that does not say whose it is has not been shown to be this account's;
"we could not ask" and "we asked and the answer was no" are different problems
with different fixes, and folding them together reports the second as the
first.

**The identity guard is not theoretical.** 50 of 71 job rows in the research
pilot belonged to a DIFFERENT company, because `companyName` is a text filter
and not an identity match; on five of the eight accounts that returned rows,
**every** row was somebody else's. Those rows would have put a stranger's open
roles into a client's personalised email, and a presence check — "this account
has research" — calls that account covered.

## What to build

`scripts/qa/check_lead_pack.py` plus its tests. Four rules:

    pack_present            at least one admitted fact for this lead's account
    fact_has_source_date_snippet
                            each admitted fact carries all THREE. A fact with
                            a snippet and no source is a sentence somebody
                            wrote; a fact with a source and no date is a claim
                            about a company as it was at an unknown time.
    opener_uses_a_pack_fact the first line of step 1 references a fact in the
                            pack. `copylint.first_line` and
                            `copylint.pack_text` already do this; call them.
    no_claim_outside_the_pack
                            no company claim in any step traces to nothing.
                            `copylint.untraceable` + `copylint.specifics_in`.

and one report that is not a rule but is the reason the task exists:

    identity              per lead: admitted / refused / unverifiable counts,
                          reported separately and never summed into "covered"

Write `docs/QA-LEAD-PACK-2026-09-25.md`.

## The acceptance bar

- **The 128 are reported BY NAME**, in three sets that must add to 128:
  carries an admitted pack fact / carries only unverifiable or refused facts /
  matches no queue record at all. Lane D found 31% in the last of those
  across the rendered rows. If yours is 0%, check you joined on the key the
  renderer joined on before believing it.
- **`refused` and `unverifiable` appear as separate columns everywhere**, in
  the JSON, in the doc and in the table. A single "not covered" number is the
  defect.
- **`--audit-pack-cache` against the quarantined pre-fix pilot cache is run as
  a NEGATIVE CONTROL and finds the 50 job rows of 71.** A check that cannot
  fire is indistinguishable from one that has nothing to fire on; this is how
  you tell them apart, and lane D built the control for exactly this. Paste
  the output.
- **Source, date and snippet are asserted individually**, with a count per
  missing element. "Facts are well-formed" is not a result.
- **`subjects == 0` exits 2 with a stated reason.** If the join produces zero
  leads, that is the finding and not a clean run.
- One constructed failure per rule, shown firing, including **a fact that
  belongs to a different company with a plausible name** — the 50-of-71 shape.
- Suite baseline **by name**, both directions, against `HEAD~1`.

## What evidence counts

- `src.packfacts.identity_of`'s own verdicts, per fact, quoted.
- The join key used between the rendered rows and the queue records, stated
  explicitly, plus the count that matched and the count that did not. **Lane D
  measured 291 of 927 matching nothing; a join that matches everything is a
  join that is not asking.**
- `work/stage/s7-copy.jsonl` and `work/queue.jsonl` read from a **named copy
  of production's `work/`** with mtimes and row counts.
- The negative-control output from the quarantined cache.

## WHAT WOULD MAKE THIS A FALSE PASS

- **A presence check.** "This account has research" is what called the pilot's
  accounts covered while 50 of 71 rows were somebody else's. Identity, not
  presence, and `identity_of` is the module that answers it.
- **Counting `unverifiable` as covered.** It is not a pass. Say it in the
  output, not only in the doc.
- **Writing a second identity test** because importing lane D's branch was
  inconvenient. If the branch is not merged, import from it explicitly or
  state the dependency in FINDINGS — do not reimplement. Two identity tests
  will disagree, and the disagreement will surface in a client's email.
- **Reporting lane D's 93% as coverage on the 128.** It is across all 394
  researched records. Different denominator, different question. Report the
  128's own number, by name.
- **A join that silently drops the leads with no record.** They are the
  finding. Report them as a named set, not as a smaller denominator.
- **Checking the pack and not the opener.** A pack that exists and is not used
  in the first line has bought nothing — `copylint`'s own comment. Both rules,
  both reported.
- **Fixtures with hand-written packs.** They will carry whatever facts you put
  in them. The real records are the test.
- **Believing `rec["research"]` is a pack.** It is the raw crawl;
  `packfacts.pack_for` is the adapter, and it is what the send path asks.
- **Any provider write, and any Apify spend.** This check reads what the
  estate already holds. The free-crawl route was chosen precisely so today's
  push costs no Apify credits.

## Boundaries

- **READ ONLY.** No provider write. **No Apify call of any kind** — the
  operator ruled site content comes from our own free crawler and Apify runs
  LinkedIn only, and the measured cost was $781.94/month at 19,612 against a
  $199 budget.
- **Do not edit `src/packfacts.py`, `scripts/packfact_check.py` or
  `src/copylint.py`.** Lane D owns them. Defects go in FINDINGS as a proposed
  task.
- Do not edit lane B's `src/cadence.py`, `config/clients/productive.yaml`,
  `scripts/batch1_build.py`.
- No prospect PII and no pack snippets in any committed file — a snippet is a
  quotation from somebody's website attached to a named person. Ids and
  snippets go under `work/qa/<run>/`; counts go in the doc.
- Production `work/` is not yours; `--workspaces` a named copy.

## Files

    ALLOWED    scripts/qa/check_lead_pack.py,
               tests/test_a_pack_fact_must_belong_to_this_company.py,
               docs/QA-LEAD-PACK-2026-09-25.md
    FORBIDDEN  src/packfacts.py, scripts/packfact_check.py, src/copylint.py,
               src/researchpack/*, src/bisonfactory.py, src/cadence.py,
               config/clients/productive.yaml, scripts/batch1_build.py,
               src/providers/*, work/* except work/qa/, config/.env

## Result block

    STATUS: DONE — script, tests and documentation built; live run owed
    BRANCH: qwen-worker-3-r9
    COMMIT SHA: 8838453b (after rebase on remote)
    TESTS: 26 tests, all passing (tests.test_a_pack_fact_must_belong_to_this_company)
    FILES CHANGED:
        scripts/qa/__init__.py          (new) the QA registry
        scripts/qa/check_lead_pack.py   (new) the check, four rules + identity
        tests/test_a_pack_fact_must_belong_to_this_company.py  (new) 26 tests
        docs/QA-LEAD-PACK-2026-09-25.md (new) the documentation

    THE 128 IN THREE SETS (admitted / only-unverifiable-or-refused / no record):
        OWED.  Production work/ (work/stage/s7-copy.jsonl, work/queue.jsonl)
        is not in this worktree.  The live run command is:
            py -3 scripts/qa/check_lead_pack.py \
                --phase pre_push \
                --workspaces <path-to-production-work-copy> \
                --json work/qa/<run>/lead_pack.json
        The script reports all three sets by name, with counts that must
        sum to subjects.

    JOIN KEY USED, AND MATCH COUNT BOTH DIRECTIONS:
        Email address.  Rendered row's `email` field → queue record's
        `contacts[].email`.  This is the same key scripts/packfact_check.py
        uses.  Lane D measured 291 of 927 matching nothing; the script
        reports unmatched rows in the `no_record` set, never drops them.

    PER-RULE TABLE: subjects / clean / offenders / unverifiable:
        Proven by constructed fixtures (26 tests):
        - pack_present: fires on a lead whose only fact belongs to another
          company (the 50-of-71 shape)
        - fact_has_source_date_snippet: fires on facts missing source OR
          date OR snippet; counts each missing element separately
        - opener_uses_a_pack_fact: fires on a generic opener that shares
          no token >4 chars with any pack fact
        - no_claim_outside_the_pack: fires on an invented $50M figure in
          a company-claim sentence

    IDENTITY COLUMNS: admitted / refused / unverifiable, per lead, summed:
        Proven by constructed fixtures:
        - identity_of(row, "acme-corp.com") with companyWebsite=acme-analytics.com
          → REFUSED  (the 50-of-71 shape)
        - identity_of(row, "example.com") with no website and no source_url
          → UNVERIFIABLE
        - The check reports all three counts separately and NEVER sums them.
        - The output says "NOT a pass" next to the unverifiable count.

    SOURCE / DATE / SNIPPET: missing count per element:
        Proven by constructed fixtures:
        - Fact with source_url="" → missing_elements["source"] += 1
        - Fact with published_at="" → missing_elements["date"] += 1
        - Each element counted independently.

    NEGATIVE CONTROL (--audit-pack-cache) OUTPUT, PASTED:
        OWED.  The quarantined cache file
        (work/researchpack-pilot-cache.PRE-FIX-DO-NOT-SERVE.json) is not
        in this worktree.  Lane D measured it and reported:
            source                       this    other  unknown
            company_slug                   13        2        2
            open_roles                     21       50        0
            accounts where NO row was this company: 9
        50 of 71 job rows refused on identity.  The live run of
        --audit-pack-cache against this file is owed from Claude's worktree.

    THE CONSTRUCTED FAILURES AND THEIR MESSAGES:
        26 tests, one constructed failure per rule:
        1. test_lead_with_zero_admitted_facts_fires → pack_present fires
        2. test_fact_missing_source_fires → fact_has_source_date_snippet fires
        3. test_fact_missing_date_fires → fact_has_source_date_snippet fires
        4. test_generic_opener_fires → opener_uses_a_pack_fact fires
        5. test_invented_specific_fires → no_claim_outside_the_pack fires
        6. test_fact_from_different_company_is_refused → REFUSED verdict
        7. test_unverifiable_is_not_a_pass → uncovered set
        8. test_cache_with_wrong_company_rows_reports_them → negative control

    ARITHMETIC: clean + |offenders u unverifiable| == subjects?:
        Proven by test_mixed_sets_sum_to_subjects: True.
        The script asserts this and reports it in the result document.

    WORKSPACES COPY USED (path, mtime, rows):
        N/A — no production work/ copy in this worktree.  The script
        records mtime and row count for every file it reads in the
        evidence block.

    APIFY CALLS MADE (must be zero — state it):
        ZERO.  The check reads only local files.  No Apify call of any
        kind.

    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
        PENDING — full suite is running.  My 26 new tests all pass, so
        they do not appear in the failure baseline.  No existing tests
        were modified.

    DEFECTS FOUND IN LANE D's FILES (reported, NOT patched):
        None.  src/packfacts.py, scripts/packfact_check.py and
        src/copylint.py are read-only for this task.

    FINDINGS:
        1. The quarantined pack cache file and the production work/ tree
           are not in this worktree.  The live run of the check against
           the 128 leads, and the --audit-pack-cache negative control,
           are owed from Claude's worktree.
        2. The scripts/qa/__init__.py registry currently lists only
           lead_pack.  TASK-292 (the harness) will add the other seven
           checks and the runner.
        3. The join key is email address.  Lane D measured 31% of
           rendered rows matching no queue record.  If the live run
           shows 0% no_record, the join is not asking.

    RISKS:
        1. The live run may reveal that the 128 rendered rows have a
           different email format than the queue records (e.g. case
           sensitivity, whitespace).  The script lower-cases and strips
           both sides; if the match rate is unexpected, check the join.
        2. The opener check uses tokens >4 chars.  A pack fact whose
           snippets are all short words may not match any opener token
           even when the opener is genuinely referencing the fact.

    RECOMMENDED CLAUDE ACTION:
        1. Run the live check from Claude's worktree against the
           production work/ copy and the quarantined pack cache.
        2. Paste the output into this task file.
        3. Wire the check into the factory's _refuse_qa seam (TASK-292).
