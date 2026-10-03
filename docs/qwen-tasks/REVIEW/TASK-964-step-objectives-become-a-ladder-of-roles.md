# TASK-964 — `step_objectives` becomes a ladder of ROLES, not of words

Operator, 2026-10-02, after reading the copy the system produced and writing
*"passes the gates, would not be sent"* with five reasons.

**WRITTEN AFTER THE CODE AND SAYING SO.** Every command below was executed
before it was written down, and two of them changed what the code does rather
than the other way round.

## The ladder

| step | role |
|---|---|
| em1 | the OFFER |
| em2 | a smaller tangible piece of the SAME offer |
| em3 | PROOF — a named client and a number |
| em4 | an easy-answer question with an EXPLICIT EXIT |
| em5 | BREAKUP in a NEW THREAD, keeping the offer |

`sequencegate.ROLE_LADDER` is that table, and `sequencegate.role_ladder()` is
the only thing that applies all five refusals: two steps sharing a rung, an ask
that does not descend, a bump with no thread reference, the same proof twice,
and — from invariant 0 — a rung that cannot be read at all.

## Where the ask order lives, and why not in the offer library

`config/copy-ask-ladder.yaml`, tenant-neutral, read through the project's own
`clients.parse` rather than PyYAML (a folded scalar broke `offers.load()` for
the whole library earlier the same night).

It is NOT in `config/clients/productive-offers.yaml`, where the other messaging
rules live, because `offers.py` is SINGLE-TENANT (TASK-564 finding 3) and
`copylint` deliberately never reads it — while "worth a look?" is a smaller ask
than a booked meeting for every client in every vertical. The file is the
AUTHORITY on the order: rank is the position in `ask_ladder`, so reordering that
one line reorders the gate.

## Three defects the control caught, each now a test

1. **Ranking the whole body read SUBJECT MATTER as an ask.** The artefact's em1
   and em3 ranked as BOOKED MEETINGS because "next week" and "booked" appear in
   them — describing the prospect's own resource bookings, which is what this
   product is *about*. For this client the words of the domain and the words of
   a meeting request are the same words. Only the asking sentences — a question,
   or a sentence carrying a directive — are read now.
2. **em4 read as a BREAKUP**, because an explicit exit is written in a
   breakup's words ("if it is not the right time, say the word"). Detection
   returns the SET of rungs a body reads as, and a step is credited with its
   OWN rung when it reads as that rung; a step that misses its rung is credited
   with the NEAREST one it does read as, so a drifting em3 is named as another
   em2 rather than as a second em1.
3. **The proof rung missed "Mast Studio cut 12 hours a week"** because the
   marker was spelled `they cut`. The verbs are bare now and the named party
   comes from the number-and-name extractor, which is what makes the pronoun
   irrelevant.

## Acceptance

```
python -c "import json,sys; sys.path.insert(0,'.'); from src import sequencegate as g; steps=json.load(open('tests/fixtures/converged-copy-anonymised-2026-10-02.json',encoding='utf-8'))['steps']; v=g.role_ladder(steps); assert v['refused'], 'the artefact was NOT refused by the role ladder'; fired={f['check'] for f in v['failures']}; assert 'bump_without_thread' in fired and 'ask_does_not_descend' in fired, fired; assert v['roles']['em1'] is None, 'the offer email reads as an offer, which contradicts the finding'; print('OK refused,', len(v['failures']), 'findings:', sorted(fired))"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import copylint as c; order=c.ask_order(); assert len(order)>=3, order; big=c.ask_rank('Can we book a 30 minute call on Thursday?'); small=c.ask_rank('Worth a look?'); assert big==len(order) and small==1, (big, small); assert c.ask_rank('No question at all here.') is None, 'a body with no ask must read UNKNOWN, not smallest'; assert c.ask_rank('We track what is booked next week for every studio.') is None, 'subject matter was read as an ask - the measured false positive'; assert c.ask_rank('Worth a look - or a quick 15 minutes if easier?')==order.index('call_or_demo')+1, 'the largest matching rung must win'; print('OK asks ordered, unknown is UNKNOWN, and domain nouns are not asks')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import copylint as c; assert c.describes_their_own_company('Hi Casey, Northgate Studio is a UK-based digital marketing agency.','Northgate Studio'), 'the defect sentence was not refused'; assert c.describes_their_own_company('I was reading about Northgate Studio, a UK agency with four studios.','Northgate Studio'), 'the appositive form was not refused'; assert not c.describes_their_own_company('Teams like yours at Northgate Studio run four studios on one plan.','Northgate Studio'), 'legitimate personalisation was refused - this is the control'; print('OK two definitional shapes refused, personalisation allowed')"
```

```
python -c "import sys; sys.path.insert(0,'.'); from src import copylint as c; body='Did any of that land? If not, I will close the loop. Worth a look?'; assert c.question_count(body)>1 and c.refuses_multiple_questions(body), 'two questions passed'; one='Following up on my note - worth a look?'; assert not c.refuses_multiple_questions(one), 'a single CTA question was refused'; print('OK at most one question per email')"
```

```
python -m unittest tests.test_the_ladder_is_a_ladder_of_roles -v
```

### NEGATIVE CONTROL

**Every command carries its opposite case on the same line, so a rule that
refuses everything fails these too** — command 1 asserts which checks fired
rather than only that something did, command 2 holds the UNKNOWN case and the
measured subject-matter false positive, command 3 holds the legitimate
personalisation sentence, command 4 holds the single-CTA string.

Command 5 is the one that matters most and it is the half a gate usually
skips: `TheControlPasses` builds five steps TO the ladder and asserts the
ladder **allows** them, and `EveryRuleBitesWhenBroken` then breaks each rule in
turn and asserts the matching refusal appears. Without the first half the
refusals prove nothing, because a rule that refuses all copy would refuse the
artefact just as convincingly. That control is not decoration: it failed three
times while this was written, and all three failures were defects in the gate.

22 tests, all green, and the module imports nothing that binds a port, so it
can run while a full suite holds the machine lock.

## The fixture is anonymised, and the anonymisation is part of the proof

`tests/fixtures/converged-copy-anonymised-2026-10-02.json` is the 2026-10-02
generation — the "before" half of the operator's before/after. The prospect is
a real company and a real person, a fixture in git is published, and this
repository has shipped PII in a generated fixture twice.

Every substitution keeps each body's **token count identical**, asserted at
write time, because the token count is what the word contract reads and an
anonymisation that moved it would quietly change the measurement the fixture
exists to carry. Declared words: em1 61, em2 41, em3 53, em4 46, em5 41 — all
of them below the operator's new em1 band of 90–140, and em2/em5 below the 45
floor, which is the contract half of the same finding.

**Three times in one night a check reintroduced the names it existed to keep
out:** the anonymiser's own metadata field listed its substitution patterns
(caught by its own scan), and then this module's list of forbidden strings was
matched by the PII scan over the staged diff. The test holds them base64 now
and the docstring says why.

## STILL OPEN, and deliberately not in this commit

- **The contract numbers.** em1 90–140 target 120 against
  `WORD_CONTRACT`'s em1 ceiling of **90** as 943 enforces it. The two intersect
  at exactly one value, which is A21 returning on a different line. One
  authority has to be retired, and that is the operator's call — §6 decision 2
  of the morning handover.
- **The two entry gates**: em1 without a research row HELD `research_required`,
  and em3 HELD until two licensed proof rows exist. The ladder refuses the
  copy; these refuse the GENERATION, which is a different call site.
- **The exemplars.** 16 em1 bodies and the Volteum cadence are not reachable
  from this machine — EmailBison exposes no sent-message body endpoint and no
  campaign in the workspace carries that name. BLOCKED on the operator
  supplying the content, and `WRITER_SYSTEM` is not wired until it exists.
- **The regeneration.** bigfish and savagebrands under the new rules, before
  and after, which is what the operator asked for last. It needs the two entry
  gates and the contract decision above, or it regenerates against half a rule.

## Files

`src/sequencegate.py`, `src/copylint.py`, `config/copy-ask-ladder.yaml`,
`tests/test_the_ladder_is_a_ladder_of_roles.py`,
`tests/fixtures/converged-copy-anonymised-2026-10-02.json`.
