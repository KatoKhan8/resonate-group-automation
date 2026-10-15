# CANARY-01 criterion 9 is UNKNOWN, not MET — the brake's path is pinned by nothing

TASK 0210 (pilotcaps), **second pass**, 2026-10-16. The first pass is
`docs/CANARY-01-EXIT-CRITERIA-RE-AUDIT-2026-10-16.md` (`62bdd8ac0`) and
recorded criterion 9 as **MET at `e84108f5d`**. This pass re-measured it and
**it is UNKNOWN.**

The task was re-dispatched by the watcher after the first pass had already
completed it, so it was re-run under the brief's own rule: *a verdict moves
only on evidence you produced in this run, not on a lane's report of its own
work* — which applies to this lane's claim about this lane's commit too.

    T1   wt-pilotcaps-2026-10-14           62bdd8ac0   CRLF (CR=15, 812 B)
    T2   resonate-trees\r-pc0210b          e84108f5d   LF   (CR=0,  797 B)
         detached at a named SHA, owned by no track, removed after the run
    origin/master                          b1f290c84   unchanged

No provider call, no network, no `--live`, no cap or gate change. **The real
`STOP-SENDING` file was asserted absent before and after every plant and was
never created.** Every plant is a source edit, restored by `git checkout --`
and verified by sha256 (`src/haltfile.py` = `34eab0a1b87a6a2a…`).

Criteria 3 and 5 reproduced the first pass exactly and their verdicts stand at
**NOT MET**; see `resonate-ops\EXIT-CRITERIA-2026-10-16.md` for the full table.
This file records only the verdict that moved, and the two findings the first
pass did not reach.

---

## 1. The mechanism works. The binding does not.

At T2, the seven STOP-SENDING brake modules:

    py -3 -B -m unittest -v \
      tests.test_no_path_reaches_a_transport_without_passing_the_stop_sending_brake \
      tests.test_bisonfactory_consults_the_stop_sending_brake_before_each_transport \
      tests.test_the_operator_can_pull_the_stop_sending_brake_alone \
      tests.test_the_stop_sending_brake_asks_nobody_for_permission \
      tests.test_the_stop_sending_brake_fails_closed_when_it_cannot_be_read \
      tests.test_the_stop_sending_brake_refuses_the_transport_immediately \
      tests.test_the_stop_sending_brake_stops_the_resume_scripts

    Ran 36 tests — OK        failing names: none

Two of three plants were caught, so the suite has real reach. Both attack
surfaces the first pass's P-series did not touch — it tested *"the brake asks
for a permission"* and *"a caller stops consulting the brake"*.

### Q1 — the unreadable-path leg fails open

    --- a/src/haltfile.py
    +++ b/src/haltfile.py
         except OSError as unreadable:
    +        return None
             raise OperatorStop(

    CAUGHT by 2
      test_a_permission_error_on_lstat_refuses_rather_than_sends
      test_any_os_error_refuses_not_only_the_two_we_thought_of

This is invariant 0 attacked directly: an unreadable authority becoming "go".
The guard holds.

### Q3 — the exemption set is widened by one verb

    --- a/src/haltfile.py
    +++ b/src/haltfile.py
     BRAKE_OPERATIONS = frozenset({
    +    "bison.resume",
         "heyreach.pause",

    CAUGHT by 1
      test_the_door_verb_set_is_the_repeatable_set

`"bison.resume"` is `providerwrites.EMAIL_RESUME`. `BRAKE_OPERATIONS` is the
set of verbs **exempt** from the brake, so adding a member is the one direction
in which a change silently creates a bypass — pulling STOP-SENDING would stop
failing to stop a resume, against a standing rule that legacy campaigns are
never resumed. The guard holds, and it holds because the set is pinned to
`providerwrites.REPEATABLE` rather than listed twice.

---

## 2. Q2 — undetected

    --- a/src/haltfile.py
    +++ b/src/haltfile.py
    -STOP_SENDING_PATH = r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING"
    +STOP_SENDING_PATH = r"C:\Users\Zvonimir\Desktop\resonate-ops\STOP-SENDING-ELSEWHERE"

    Ran 36 — OK.    UNDETECTED.

**Why nothing saw it.** All 36 tests patch `haltfile.STOP_SENDING_PATH` to a
temp path — correctly, since no test of this repository may create the real
file. So no test ever exercises the default value. The one path-related test
asserts only the path's *properties*:

    test_the_path_is_a_constant_not_derived_from_the_running_tree
      assertTrue(os.path.isabs(STOP_SENDING_PATH))
      assertNotIn(ROOT, STOP_SENDING_PATH)
      assertNotIn("resonate-group-automation", STOP_SENDING_PATH)

`…\resonate-ops\STOP-SENDING-ELSEWHERE` satisfies all three. **The path is
pinned for what it is like, never for what it is.**

### The stronger plant is caught — and only incidentally

    STOP_SENDING_PATH -> r"C:\Temp\nowhere\BRAKE"
    Ran 36 — FAILED (errors=2).    CAUGHT.

That is not the value being pinned. It is the fail-closed leg firing because
the **parent directory does not exist**:

    parent exists=False  C:\Temp\nowhere\BRAKE
         FileNotFoundError winerror=3  ->  REFUSES (unknown)
    parent exists=True   ...\resonate-ops\STOP-SENDING-ELSEWHERE
         FileNotFoundError winerror=2  ->  RETURNS None (go)
    parent exists=True   ...\resonate-ops\STOP-SENDING
         FileNotFoundError winerror=2  ->  RETURNS None (go)

So detection depends on the parent being absent. **The realistic drift — a typo
in the leaf, a renamed file, a reorganised `resonate-ops` — keeps the parent
and therefore fails OPEN**, silently, with 36 green tests.

### The consequence, with a control

Run entirely in temp directories; the real brake file was never touched:

    operator created :  <tmp>\STOP-SENDING              True
    code would stat  :  <tmp>\STOP-SENDING-ELSEWHERE    False

      RESULT: require_released() returned None  ->  SENDS PERMITTED
              The operator believes the brake is pulled. It is not read.

      CONTROL: pointed at the operator's own file, it REFUSES. Harness works.

And the other half of the binding is not in the repository at all:

    grep -rn "STOP-SENDING" docs/ *.md        (at T2)   ->  no matches

There is no committed operator-facing instruction naming the path. Where that
instruction does live — the lane files, outside this repository — nothing
compares it to the constant.

---

## 3. Verdict and the fix

**UNKNOWN at `e84108f5d`.** Per the brief: a planted violation the criterion
should catch went undetected, and an undetected plant makes the verdict
UNKNOWN, not MET. **NOT MET at T1**, where `src/haltfile.py` does not exist.

To be fair to what was built: **the brake works.** It refuses when pulled, it
fails closed on an unreadable path, it does not disable the four brake verbs,
and it asks nobody for permission — 36 tests and two of three plants say so.
What is unverified is the **binding between the file the code stats and the
file the operator is told to create.** Criterion 9 is the one criterion where
that is fatal: a switch reading the wrong file is not a switch the operator can
operate alone, and it fails in the direction of sending.

**Next action: CONSTRUCTION. Small. Nobody's decision.**

1. One test asserting the **literal value** of `STOP_SENDING_PATH`. Cheap, and
   it closes Q2.
2. Better, because it removes the second representation rather than pinning
   it: a committed operator card under `docs/`, **generated from the constant**,
   so the instruction and the code cannot diverge. The existing
   `test_the_operator_can_pull_the_stop_sending_brake_alone` already builds its
   pull/release commands by formatting the constant — that generation just has
   no committed output.

Then the integration problem the first pass named remains: `e84108f5d` must
reach a tree that also holds criteria 1, 2, 4 and 7's mechanism, which today is
T1's lineage and does not contain it.

---

## 4. Two findings the first pass did not reach

### Criterion 3 has three authorities, and two contradict each other

The first pass concluded *"there are not two authorities shipping; there is
one, and it ships empty."* The graph half reproduces —
`config/linkedin/productive-standard.json` carries `{connection_note}` zero
times and `heyreach.connection_notes(graph)` returns `['']`. But
`config/clients/productive.yaml:400`, the canary client's own config, says:

    linkedin_connection_note:
      mode: llm

and its comment asserts a fact about the graph: *"each step's copy travels per
lead in a custom field named after the step's graph role and the graph carries
`{connection_note}`, `{connected_1}` and so on. HeyReach does NOT error on a
variable it cannot fill — it sends `fallbackMessage` instead, silently."*

The graph carries no such placeholder, and a third representation exists: the
same file declares a real fallback sentence for `connection_note` which the
graph's own `fallbackMessage` (`""`) does not carry.

`heyreach.sequence_hazards` **does** see the defect, and it discriminates —
checked rather than assumed:

    as shipped       -> ('the connection request carries no note at all', [])
    note filled      -> no note hazard          <- the instrument discriminates
    whitespace-only  -> still flagged           <- whitespace does not fool it

But nothing enforces it. The only gate that reads notes, `configdiff.py:516`,
refuses on `len(notes) > 1`; `['']` has length 1 and passes. Two further
hazards on the same graph: `{Icebreaker}` is used and not supplied, and
`heyreach.linkedin_only(graph)` is `False` — `SEND_LEAD_TO_BISON` to 417/418.

**So either answer to criterion 3 owes a fix.** If the no-note decision is
reversed, `mode: llm` sends the words per lead into a field with no slot,
HeyReach substitutes `fallbackMessage`, and that is `""` — so the note renders
**empty anyway, silently**, which is the exact failure criterion 3 exists to
prevent. If the criterion is rewritten instead, `mode: llm` and the declared
fallback are dead configuration asserting something false about the graph.

### Criterion 5's analyzer has proven reach, and the pin's two failures are attributed

`26 of 58` is the number everything rests on, so it was attacked. One new
ungated mutating call site planted under `scripts/`:

    baseline        write paths 58   BYPASS 26
    with the plant  write paths 59   BYPASS 27
      BYPASS  scripts/_plant_probe_0210b.py:6  bison.pause_campaign in an_ungated_write()
    restored        write paths 58   BYPASS 26      tree clean

The denominator is a measurement, not a blind count.

And `tests/test_no_new_write_bypasses_the_door`'s two failures at T1 are no
longer merely disclaimed as "not pilotcaps'" — they are attributed:

    git log -1 -- scripts/batch_linkedin_push.py     97fec582d  (glm-c TASK 0170)
    git log -1 -- scripts/known_write_bypasses.json  7a2890022  (pilotcaps 0160)
    git show 97fec582d -- scripts/batch_linkedin_push.py
      +def stage_rows_to_list(list_id, rows, pace=0.0,
      +                   heyreach.add_leads_to_list(payload["listId"], [_lead]),
      -                   heyreach.add_leads_to_list(
    neither 008aa86dd nor 62bdd8ac0 touched either file

`glm-c/0170` moved the call out of `main` into a new `stage_rows_to_list`; the
baseline was last regenerated by `pilotcaps/0160`, before that. The pin is
reporting a real rename drift from glm-c 0170. **Do not regenerate the baseline
to make it green.**

---

## 5. Not measured

**No full suite was run, in either pass. The merge gate for this branch is
UNMET and the branch is not proposed for master.** Criteria 1, 2, 4, 6, 7 and 8
were out of scope; 6 and 8 rest on artifacts outside the repository and are
**UNKNOWN** on either tree.

Plant harnesses, kept so both passes reproduce:
`resonate-ops\pilotcaps-0210b-plants.py` (Q1/Q2/Q3) and
`resonate-ops\pilotcaps-0210b-q2b.py`. The plant diffs are inlined above so
this file reproduces them without that folder.

To recreate T2: `git worktree add --detach <path> e84108f5d`.
