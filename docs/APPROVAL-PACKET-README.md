# The approval packet lives outside git, deliberately

TASK-200 built the packet that makes the human read cheap: per record, per
step, the rendered copy as a prospect would receive it, the lint and claims
verdicts beside it, the evidence row behind every claim, the fallback and
`persona=None` flags, ordered so the cheapest decisions come first.

It is **not committed**, and that is the right answer rather than a compromise.

## Why

An approval packet has to carry the copy a prospect will actually receive. That
copy names the company, and rendering it with the names hashed would defeat the
purpose - an operator cannot approve a message they cannot read. So the packet
is real prospect data by construction, 7,980 lines of it.

`work/` is gitignored for exactly this class of thing. `CLAUDE.md`: "`work/`
stays gitignored. It is 300 real companies and 92 real contacts and it is not
ours to publish."

The PII guard refused the packet on its first commit, which is the guard doing
its job. TASK-200 was told in advance to report that refusal rather than defeat
it, and the resolution is to move the artefact rather than to weaken the check
or to hash the copy into uselessness.

## Where it is, and how to regenerate it

    work/approval/APPROVAL-PACKET-2026-09-16.md     the packet
    scripts/task200_approval_packet.py              the generator, committed

Regenerate with the generator. It reads live state, so a packet is only as
current as the moment it was written - and approval is taken against a
fingerprint, so a packet generated after copy changed describes copy nobody
approved.

## What reading it commits you to

Per `OPERATOR-AUTHORIZATION-2026-09-16.md`, approval means `approval.by` is set
to the operator, and a step with operator approval is a step that may reach a
person once its campaign is live. The packet states, per record, which campaign
a contact would enter, how many messages they would receive, over how many
days, and from which sender.

Nothing in this repository may set `approval.by` on the operator's behalf.
That is the whole point of the packet: it exists so the decision is informed,
not so it can be delegated.
