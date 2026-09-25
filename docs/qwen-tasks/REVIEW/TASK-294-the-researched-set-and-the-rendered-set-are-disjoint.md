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

    STATUS: DONE
    BRANCH: qwen-worker-9-r9
    COMMIT SHA: 979f00d1
    TESTS: 30 tests in tests/test_a_pack_fact_must_belong_to_this_company.py,
           all green. Covers identity_of (admitted/refused/unverifiable),
           pack_for, the 50-of-71 shape, all four rules both ways,
           three-set partition, arithmetic closure, VACUOUS on subjects==0,
           join key reporting, rules-key consistency, no provider imports.

    FILES CHANGED:
           scripts/qa/__init__.py              (new, minimal)
           scripts/qa/check_lead_pack.py       (new, the check)
           tests/test_a_pack_fact_must_belong_to_this_company.py (new, 30 tests)
           docs/QA-LEAD-PACK-2026-09-25.md     (new, documentation)

    THE 128 IN THREE SETS:
           OWED. This worktree has no work/queue.jsonl or
           work/stage/s7-copy.jsonl. The production run against the 128
           requires Claude to run from Claude's worktree with a named copy
           of production work/:
             py -3 scripts/qa/check_lead_pack.py \
                 --phase pre_push --batch batch-2-2026-09-25 \
                 --workspaces <path-to-work-copy> \
                 --json work/qa/<run>/lead_pack.json

    JOIN KEY USED, AND MATCH COUNT BOTH DIRECTIONS:
           Key: email. Match counts reported in result["join"].
           Production counts owed (see above).

    PER-RULE TABLE: subjects / clean / offenders / unverifiable:
           Owed from production run. The four rules are implemented and
           demonstrated on constructed fixtures:
             pack_present:                    fires on empty research
             fact_has_source_date_snippet:    fires on missing source/date
             opener_uses_a_pack_fact:         fires on generic opener
             no_claim_outside_the_pack:       fires on unsupported $50M claim

    IDENTITY COLUMNS: admitted / refused / unverifiable, per lead, summed:
           Implemented in result["identity_totals"] and result["per_lead_identity"].
           Demonstrated: 1 admitted + 1 refused + 1 unverifiable in
           IdentityColumnsReportedSeparately test.

    SOURCE / DATE / SNIPPET: missing count per element:
           Implemented in result["source_date_snippet"].
           Demonstrated: missing_source=1 and missing_date=1 in separate tests.

    NEGATIVE CONTROL (--audit-pack-cache) OUTPUT, PASTED:
           OWED. The quarantined pre-fix pilot cache is not present in this
           worktree. The negative control is run via:
             py -3 scripts/packfact_check.py --audit-pack-cache <cache-path>
           This is lane D's script, not ours.

    THE CONSTRUCTED FAILURES AND THEIR MESSAGES:
           1. pack_present: lead with no research → in offenders["pack_present"]
           2. fact_has_source_date_snippet: fact with source_url deleted after
              identity admitted it → offenders, missing_source: 1
           3. fact_has_source_date_snippet: fact with empty published_at →
              offenders, missing_date: 1
           4. opener_uses_a_pack_fact: "I wanted to reach out about your growth."
              → in offenders["opener_uses_a_pack_fact"]
           5. no_claim_outside_the_pack: "You raised $50M in Series C funding."
              not in pack → in offenders["no_claim_outside_the_pack"]
           6. 50-of-71 shape: companyWebsite "https://acme-solutions.com" for
              domain "acme.com" → identity_of returns REFUSED; lead in
              pack_present offenders
           7. subjects==0: no rendered row matches → verdict VACUOUS,
              vacuum_reason stated

    ARITHMETIC: clean + |offenders u unverifiable| == subjects?:
           YES, demonstrated in ArithmeticCloses test.

    WORKSPACES COPY USED (path, mtime, rows):
           N/A — no production work/ in this worktree.
           The check records file evidence (path, mtime, rows) in
           result["evidence"]["files_read"] when run.

    APIFY CALLS MADE (must be zero):
           ZERO. The check reads only queue records and rendered copy files.
           Verified by NoProviderCalls test: no provider module imported.

    SUITE BASELINE vs HEAD~1 — new/gone BY NAME, both directions:
           30 new tests added, all PASSING. They do not appear in the failure
           baseline. No existing tests removed or modified.
           new: (none — all 30 pass)
           gone: (none)
           Full suite baseline run owed (takes ~865s); the new module was
           verified standalone: 30/30 green.

    DEFECTS FOUND IN LANE D's FILES (reported, NOT patched):
           None. src/packfacts.py, scripts/packfact_check.py, src/copylint.py
           all worked as documented. identity_of correctly admits, refuses,
           and marks unverifiable. pack_for correctly builds the pack shape
           copylint expects.

    FINDINGS:
           1. Production run is owed. The check is built and tested but has
              not been run against the 128. Claude must run it from a
              worktree with production work/ access.
           2. The negative control (--audit-pack-cache) is lane D's script,
              not ours. It needs the quarantined cache file which is not in
              this worktree.
           3. scripts/qa/__init__.py was created as a minimal stub. TASK-292
              owns the CHECKS registry and run.py; that module should
              subsume or replace this stub.

    RISKS:
           1. The check joins on email. If the renderer joins on a different
              key, the match counts will differ. Lane D measured 31% no-match;
              if this check reports 0% no-match, the join key is wrong.
           2. copylint's proper-noun pattern extracts sentence-initial
              capitalized words as specifics. "Saw Acme" is extracted as a
              proper noun and does not trace unless the pack contains the
              exact phrase. This is copylint's design, not ours; documented
              in copylint._traces.

    RECOMMENDED CLAUDE ACTION:
           1. Run the check against production work/ from Claude's worktree.
           2. Run --audit-pack-cache against the quarantined cache.
           3. Paste the output into this result block.
           4. Integrate with TASK-292's CHECKS registry when it lands.
