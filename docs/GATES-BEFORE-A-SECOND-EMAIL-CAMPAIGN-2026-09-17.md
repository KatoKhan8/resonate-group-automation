# What stands between here and ONE new authorized Productive email campaign

Traced through the code on 2026-09-17, not inferred from the permission
table. **An earlier reading of this session got it wrong in the pessimistic
direction and the correction matters**: `EMAIL_ADD_LEAD` and
`EMAIL_ASSIGN_SENDER` are NOT the gates they look like, because the staging
path does not go through `providerwrites.perform` for either of them.

## The path that actually runs

`bisonfactory.stage(canonical_campaign_id, live=True)`:

    step                 how it is gated                         status
    -----------------------------------------------------------------------
    _find_or_create      providerwrites.perform                  OPEN
                         EMAIL_CREATE_CAMPAIGN - SUPPORTED,
                         unconditional. Creates a DRAFT.
    _ensure_limits       direct call                             OPEN
    _ensure_schedule     direct call                             OPEN
    _ensure_senders      DIRECT `bison.attach_senders`.          OPEN
                         NOT providerwrites. Binds whatever
                         the canonical row's senders.email
                         names; binds nothing if it names
                         nothing, deliberately - "choosing an
                         inbox would be choosing who a
                         prospect hears from".
    _ensure_sequence     providerwrites.perform                  OPEN
                         EMAIL_SET_SEQUENCE - SUPPORTED,
                         unconditional.
    _ensure_leads        DIRECT `bison.create_lead` +            BLOCKED
                         `bison.attach_leads`. NOT               on approval
                         providerwrites - the module says so
                         in terms and names the workspace
                         killswitch as the control instead.
                         `sending.live` for productive reads
                         ON. **But `_approved_copy` returns
                         only APPROVED words and
                         `_ensure_leads` refuses a lead whose
                         step copy is missing, stopping the
                         WHOLE run rather than skipping one.**
    ACTIVATION           providerwrites.perform                  BLOCKED
                         EMAIL_ACTIVATE - SUPPORTED but          on a grant
                         CONDITIONAL on
                         `_is_the_authorized_email_campaign`,
                         which resolves the permitted provider
                         id from canonical row
                         `productive-email-control-v3` and
                         therefore refuses every campaign but
                         487.

## So the gate list is TWO operator decisions, not four permission grants

**1. APPROVAL of the contacts.** This gates STAGING, not just sending - the
factory cannot create a lead whose approved copy does not exist, and it stops
the entire run rather than staging a partial cohort. So nothing can be
pre-built while approval is outstanding, and that is the system working
correctly rather than an obstacle to route around. 17 near-miss contacts
(5 email, 12 LinkedIn) pass every other gate; `approve.approve_step` is the
action and a person takes it.

**2. THE ACTIVATION SCOPE.** `EMAIL_ACTIVATE` names one campaign. Widening it
is one code change and a new operator decision - the condition's own docstring
says "editing the tuple above to add a campaign is not a refactor".

## What is NOT a gate, corrected

- **`EMAIL_ADD_LEAD` absent from `SUPPORTED` does not stop lead staging.**
  `bisonfactory._ensure_leads` calls the transport directly and says why. The
  permission constant governs `providerwrites.perform` callers; the factory
  is not one. The scoped predicate added today
  (`_is_a_draft_campaign_this_deployment_staged`) is still worth having - it
  is what makes granting the verb a small decision rather than a
  workspace-wide licence - but it is not on this critical path.
- **`EMAIL_ASSIGN_SENDER`'s conditional does not stop sender binding** for the
  same reason.
- **Creating the campaign and writing the sequence need nothing new.**

## The sender a new campaign would use

Three inboxes have a forward book that is empty **by construction** rather
than by sample - they are attached to no ACTIVE campaign at all, only to
draft 418, which holds 225 senders and zero leads and schedules nothing:

    sender  connected  health    daily_limit  human (hashed)
     3941      yes     warming        15      9e58861fb87e
     3930      yes     warming        15      7cc85aecf642
     3919      yes     warming        15      2b4e867056bc

All three are `warming` rather than `ok` - warmup is why they are idle - and
none has an attested human owner, because `HUMAN_IDENTITY_ATTESTED` is 0
across all 225 inboxes. A campaign can still name one on its canonical row,
which is exactly how 487 names 2736; what it cannot do is have
`assignment.allocate` choose one, and that is a different question from
whether a campaign can send.

## Why this does not make the 18th reachable on its own

Both decisions are the operator's, and the first one gates the second: there
is nothing to activate until there is a staged cohort, and there is no staged
cohort until the contacts are approved. If both arrive, the build itself is
minutes of provider calls and a scheduler run on resume.

If neither arrives, 487 sends on 2026-09-23 and that is the safe outcome.
