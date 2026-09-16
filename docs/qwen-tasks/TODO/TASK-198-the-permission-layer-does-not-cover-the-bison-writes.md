PRIORITY: P0
DEPENDS:

# TASK-198 - four EmailBison writes go round the permission layer

## WHERE THIS SITS

`src/providerwrites.py` is described everywhere in this repository as "the
single door". `SUPPORTED` is what an auditor reads to answer "what can this
system write". On 2026-09-16 Claude read it that way, wrote a document saying
no verb that adds a person to an EmailBison campaign is authorized, and was
wrong.

`bisonfactory` calls four transports directly, without going through
`providerwrites.perform`:

    _ensure_limits   -> bison.set_limits
    _ensure_senders  -> bison.attach_senders
    _ensure_leads    -> bison.create_lead, bison.attach_leads

The code knows. `_ensure_leads` says so in its own comments - "bypassing
`executionguard.authorize()` and every gate it runs" - and compensates with
gates of its own: a workspace killswitch check, an account-level collision
check via `collision.check_account`, an approval check, and a cap applied
before leads are attached. Those were added after measured incidents and they
are real. Nineteen contacts were staged into campaign 481 with nine already in
the client's own campaigns and nothing objected; that is why the collision
check is there.

So this is not "the gates are missing". It is that **the write surface has two
doors and only one of them is enumerated**, and the enumerated one is the one
everybody reads.

## THE QUESTION

1. **Enumerate both doors.** Every provider write this system can perform, and
   for each: does it route through `perform`, or is the transport called
   directly, and which gates actually apply. Do HeyReach as well as EmailBison
   - `heyreachfactory` may have the same shape and nobody has checked.
2. **Then decide what to change, and argue it.** Two honest options:

     (a) route the four through `perform`, so `SUPPORTED` means what it says.
         `perform` demands an `executionguard.Authorization` for a
         prospect-facing operation, so `create_lead` and `attach_leads` would
         need one - which is a real behaviour change to the staging path and
         could refuse work that currently succeeds.

     (b) leave the calls, and make `providerwrites` state plainly that it is
         not the complete surface, with a pointer to the factory gates.

   (a) is better if it can be done without weakening the factory's own checks.
   (b) is honest and cheap. Recommend one with reasons; if (a), say exactly
   what would newly refuse.
3. **Implement only the safe half now.** Whatever you recommend, do this
   regardless: add a test that FAILS if a new direct-transport call appears in
   a factory without being declared somewhere. The defect that produced this
   task is that nothing noticed, and a test is what notices.
4. **Correct the documentation.** `providerwrites.py`'s module docstring and
   any doc describing `SUPPORTED` as the complete write surface. Point at the
   enumeration from item 1.

## THE TRAP

Do not "fix" this by adding the four verbs to `SUPPORTED`. That makes the
tuple look complete while changing nothing about which code path runs, and the
next auditor is misled in the same direction with more confidence. Membership
of `SUPPORTED` is an operator authorization and adding one is not yours.

Second trap: do not remove or bypass a factory gate while routing a call
through `perform`. The killswitch, collision, approval and cap checks in
`_ensure_leads` must all still run, in the same order, before any lead is
created. If routing through `perform` would duplicate a check, duplication is
the correct outcome here - two gates asking the same question is not a defect.

## WHAT YOU MAY NOT DO

- No provider writes. Reads only. Test against fakes.
- Do not add anything to `SUPPORTED` or `CONDITIONAL`.
- Do not remove, reorder or weaken any check in `_ensure_leads`,
  `_ensure_limits` or `_ensure_senders`.
- Do not change what `stage()` does to a campaign in the success path without
  saying so explicitly in the deliverable.
- Never commit a key, an email address, a domain or a contact name.

## FILES ALLOWED

    src/providerwrites.py   (docstring and the enumeration only - NOT SUPPORTED
                             or CONDITIONAL)
    src/bisonfactory.py   src/heyreachfactory.py   (only if you recommend (a))
    tests/test_write_surface_enumeration.py   (new)
    docs/TWO-DOORS-2026-09-16.md   (new)

## FILES FORBIDDEN

    work/   config/

## DELIVERABLE

Both doors enumerated with the gates that actually apply to each, on both
channels; an (a)-or-(b) recommendation with what would newly refuse under (a);
the test that fails when an undeclared direct transport call appears; and the
documentation corrected.
