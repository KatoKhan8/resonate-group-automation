PRIORITY: P0
SIZE: L
DEPENDS:

# TASK-313 — audit the current state against ARCHITECTURE-UPGRADE-SPEC sections 3 to 12

**Read `docs/ARCHITECTURE-UPGRADE-SPEC.md` first. It is the operator's own
text, saved verbatim, and it is not to be edited.**

**THIS IS AN AUDIT. You implement nothing.** No code changes, no new modules,
no provider writes, no campaign activation, no sending. The output is one
document: `docs/AUDIT-2026-09-26.md`, **due 08:00 on 2026-09-26.**

## THE OPERATOR OVERRIDES — these win where the spec differs

1. **We run on Hetzner, not Railway.** Section 11 lists "Railway deployment".
   Audit the deployment we actually have.
2. **No Google Reviews and no Reddit in phase 1.** Section 5 mentions Google
   Reviews; it is out for now. Do not scope it and do not research it.
3. **Five skills to start**, not fourteen: account research, offer
   development, campaign strategy, cold email writing, LinkedIn writing.
   Audit what exists for those five only.
4. **The Second Brain is built on what exists** - `config/clients/productive.yaml`,
   the existing playbooks, `contextpack`, and `docs/`. **One source of truth
   per fact, with source and date. NEVER a parallel store.** If your audit
   recommends a new store for something already in productive.yaml, that
   recommendation is wrong and the operator will say so.
5. **Offers need client-approved commercial terms.** The Offer Engine ships
   with the six real capabilities and **flags every missing offer, case study
   and asset** for the operator to obtain from the client. It invents nothing.
6. **Cheap models (Groq, Qwen) for research, extraction, relevance and
   semantic checks. Sonnet only for prospect-facing text.**
7. **Every existing gate stays**: the five-step cadence with threading as
   decided, review approval, provider ceilings, suppression, copylint,
   sequencegate.

## What the audit must contain, per section A of the spec

For each area in sections 3 to 12: **what exists, the files and functions by
name, what works on the evidence you gathered, what is incomplete, what is
duplicated, what is built but not connected to any workflow, what needs live
validation, and what should not be touched.**

**Separate CONFIRMED BUGS from ARCHITECTURAL RECOMMENDATIONS.** A bug is
something you reproduced. A recommendation is an opinion about design. The
operator reads these differently and conflating them wastes their time.

**Do not claim a test passes unless you ran it.** Paste the command and the
summary line. "The suite is green" without a run is the single most common
false claim in this repository and it has cost real hours.

## Places worth looking, because they are already built and easy to miss

    src/playbooks.py          the existing playbook architecture
    src/contextpack.py        context assembly
    src/signals.py            signal collection
    src/priority.py           scoring
    src/accountintel.py       account intelligence, if present
    src/copyprompts.py        stages A and B of the copy engine
    src/copystages.py         stages C, D, E and the writer
    src/sequencegate.py       the sequence-level gate
    src/copylint.py           per-message rules
    src/bisonfactory.py       staging, the empty-render gate
    src/providers/heyreach.py the LinkedIn cadence and its real limits
    src/reviewapproval.py     the activation gate
    src/spendledger.py        ceilings, units, reservations
    src/learning*.py          whatever learning exists
    docs/COPY-ENGINE-SPEC-v2.md  the copy strategy already agreed

**Trace the implementation rather than judging by filename.** The recurring
defect in this repository is a thing computed correctly that nothing
downstream reads: an evaluator returned INSUFFICIENT_DATA forever because
nothing wrote the field it read, and 10,957 research facts currently feed no
email at all. **Ask of every component: who reads its output?** A component
with no reader is the finding, not the component.

## Two things the operator will want called out specifically

**The HeyReach cadence.** Section 1 says preserve the existing multi-step
architecture. Before recommending anything, establish **what it actually
does today**: how many steps are configured, which ones ever render, and
which are dropped. A previous measurement found ONE LinkedIn step surfacing
from a six-step graph because generated steps with no stored copy are
silently dropped. Verify whether that is still true.

**The cross-channel stop.** The spec asks to preserve "cross-channel reply
detection and stopping". LinkedIn to email is measured and works. **Email to
LinkedIn is NOT verified**: `StopLeadInCampaign` 404s on a lead HeyReach's own
read endpoints report as present. Say so plainly in the audit rather than
listing it as working.

## What would make this audit worthless

- Recommending a parallel store for facts that live in productive.yaml.
- Listing modules that exist without saying who consumes their output.
- Claiming tests pass without the command and its output.
- Scoping Railway, Reddit or Google Reviews.
- Proposing fourteen skills when the operator asked for five.
- Confusing "not visible in the UI" with "not implemented".
- Any code change at all. This is an audit.

## Acceptance

`docs/AUDIT-2026-09-26.md` exists, covers sections 3 to 12, names files and
functions, separates confirmed bugs from recommendations, and every test claim
carries the command that produced it.

Post it and stop. Claude reads it and writes the phase 1 plan for the
operator; you implement nothing until that plan is approved.
