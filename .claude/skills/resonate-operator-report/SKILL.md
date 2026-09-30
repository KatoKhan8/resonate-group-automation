---
name: resonate-operator-report
description: Write an operator status update for Zvonimir in #resonate-os, or ask him for a decision. Use whenever you are about to post to #resonate-os, write a status/progress update, report that something is done or blocked, or need an operator choice. Enforces plain Croatian, the CLAIM/AUTHORITY/MEASURED AT/STATE block, the 🔴 decision format, milestone-only cadence, and the rule that UNKNOWN never becomes PASS.
---

# Operator report

Canonical rules: `docs/OPERATING-MODE.md` sections **KOMUNIKACIJA S OPERATEROM**
and **OPERATER FEED**, invariant **0** and registry **§0a**, decision **24**.
Notification layer: `SLACK-NOTIFICATIONS.md` (two levels, no fallback between
them). Channel resolution is `notify.ops_channel()` — never a hardcoded id, and
`C0C34GCAR27` is retired.

## Before you write anything

Ask the FOCUS RULE question (decision 20). The operator receives exactly two
things: **decisions that block the critical path or change safety**, and **the
artifacts he reviews**. Everything else is filed as a task with evidence and
gets at most one line in the next update. A finding you raise in conversation
instead of filing is lost; a filed one is preserved.

Cadence: **only when something significant changes**, or roughly hourly while
work is running. Never one update per small task.

## Language

Croatian, plain, the owner's language, no jargon. **Never** line numbers,
function names, test-framework detail, or SHAs (SHAs only when a decision needs
one). Technical identifiers stay exactly as they are in the code and are not
translated: test names, file paths, task names, field names, commands.

Technical detail belongs in GitHub and in the handoff, not in the feed.

## Every claim about state carries four fields

    CLAIM        što se tvrdi, jednom rečenicom
    AUTHORITY    koji kanonski autoritet je to rekao, imenom
    MEASURED AT  kad je mjereno
    STATE        VERIFIED / UNPROVEN / UNKNOWN

A claim with no authority does not go in the feed. Pick the authority from the
**§0a registry**, not ad hoc — the registry's third column names the plausible
source that is NOT the authority, and that is always the one used by mistake.

**`UNKNOWN` is never written as PASS, zero, empty, idle, done, safe or ready.**
If the canonical authority cannot be read, the state is UNKNOWN and stays
UNKNOWN.

**A test count is never evidence.** Neither is a green suite, a passing unit
test, a document saying "integrated", a branch existing, or an interceptor that
never fired. A PASS names four things: the real production path exercised, the
negative control, the killed mutation, and the provider readback where a
provider is involved.

Use the status ladder and never skip or infer a rung:
`ABSENT · IMPLEMENTED · UNIT_TESTED · INTEGRATION_TESTED · LIVE_VALIDATED ·
PRODUCTION_ACTIVE`.

## Numbers in a headline carry their phase name

Never a bare "ready". Write `COPY_READY`, `COLLISION_CLEAR`, `PROVIDER_READY`.
"500 spremnih" means nothing until it says ready for WHAT — the difference
between "the copy is written" and "the provider would accept this" is the whole
difference between a demonstration and the work.

## Closing block on every larger update

Tick boxes **only from the actual state of the machine**, never from intent.

    PUT DO PRVOG PRAVOG TESTA
    [ ] Offer A/B · Backup · Slack alerting · Qwen raspodjela posla
    [ ] EmailBison blocker · Canonical SequencePlan · Novi generation path
    [ ] Safety provjera · ONE-ACCOUNT test · Moj review · 10 accounta

    TRENUTNO RADIMO: [jedna rečenica]
    SLJEDEĆE: [jedna rečenica]
    TREBAM OD TEBE: [ništa / konkretna odluka]
    STVARNI PROSPECTI: Ništa poslano. Provider writes = 0.

## "Ništa poslano" means nothing sent BY THIS WORK

Decision 24, and it is not pedantry. That line has never meant "nothing was ever
sent" and must never be written to suggest it. Three things **were** sent to real
people and stay on the record: 503/504/505 (64 emails carrying another agency's
pitch signed with the operator's name), the 2026-09-23 blank-subject send (77
emails, 76 suppressed, four replied), and a LinkedIn message seven minutes after
a prospect said no. Separately, the provider confirms 912 sends against one
recorded touch.

So say which claim you are making: *this work sent nothing*, and the historical
incidents are recorded elsewhere and unchanged. **Never write "nothing has ever
been sent".** Derive the send figure, never quote it from prose — the provider is
the authority (§0a-i), and ledger absence is never absence of a send.

Also §0c: historical provider action and current eligibility are two claims and
both are always reported. *"current qualification: rejected; historical sends:
18"* — never "not qualified, therefore never contacted".

## Asking for a decision

**One decision per message. Never two.** With two in one block the operator
answers the first and the rest are lost.

    🔴 TREBAM TVOJU ODLUKU

    PROBLEM:     [jedna do tri rečenice, bez žargona]
    OPCIJA A:    [što se dogodi]
    OPCIJA B:    [što se dogodi]
    PREPORUKA:   A ili B
    ZAŠTO:       [jedan razlog]

    Odgovori "A" ili "B".

Ask only when the unresolved decision is an **irreversible external action**
(provider write, real send, real credit spend, production deployment,
destructive data mutation), a **new** decision that materially changes safety,
prospect-facing behaviour, licensed claims, approval semantics or the TASK-425
acceptance criteria, or business semantics ambiguous enough that guessing builds
the wrong product.

**Do not ask the operator to reconfirm a decision already approved.** Local
reversible work is decided, not asked about — never ask whether to continue,
commit, run tests or fix something. Unrelated safe work continues while one path
is stopped for a question.
