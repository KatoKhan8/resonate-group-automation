# CANARY-01 mailbox allowlist — by owner, not by mailbox

TASK 0020 (GLM-C), 2026-10-15. The canary may attach only mailboxes named
here, and only after the currency check in the last section. UNDECIDED and
EXCLUDED are both excluded. **Unknown is not a pass.**

Addresses are not in this file and never will be: mailboxes are identified
by provider id. `scripts/email_sender_estate.py` is the id-to-address
printer and stays the only place the roster exists in clear. Real owners
appear here as `px-` hashes (task189 salt over the NFC-normalised signature
name) plus their roster id; the three fictitious names appear in clear
because the operator has already published them in
`docs/OPERATOR-AUTHORIZATION-2026-09-21-BATCH-1.md` and three other tracked
documents.

## Method: what "real person" means, and where its authority comes from

Ownership is a human statement, never an inference from provider data —
that is `src/senderownership.py`'s entire reason to exist, and it is the
definition this allowlist uses. Three committed authorities decide it:

1. **The fictitious declaration (negative, exhaustive).** The operator's
   verbatim condition of 2026-09-21: *"No Casey Wright, Morgan Ellis or
   Riley Parker mailbox anywhere."*
   (`docs/OPERATOR-AUTHORIZATION-2026-09-21-BATCH-1.md`.) Confirmed
   2026-10-14 in `resonate-ops/CANARY-01.md`: the owner confirmed these
   three names — 51 mailboxes, 28% of the estate — are fictitious people.
   The declaration is exhaustive by the operator's own arithmetic: 51 is
   exactly these three names' holdings, identically in the 2026-09-21
   export (this fixture) and the 2026-10-14 export (CANARY-01).

2. **The recorded attestations (positive).**
   `docs/ATTESTATION-READY-2026-09-21.md`: five mailboxes attested to four
   roster humans on the operator's wording, 2026-09-21T12:02:10Z —
   eb-2736 → bojan, eb-2737 → bernarda, eb-2738 → ivan, eb-2739 → kresimir,
   eb-2740 → bernarda (2737 and 2740 are one human with two inboxes,
   exactly as the operator stated). By the evening of the same day eight
   humans were attested — campaigns 491–498 ran one per attested human:
   kresimir, bernarda, ivan, fran, tomislav, bojan, jakov, luka
   (`docs/PRODUCTION-HANDOFF-2026-09-21-NIGHT.md`), which is also where
   "154 bound of 159" attested mailboxes is recorded.

3. **The owner field.** The estate fixture
   `tests/fixtures/sender-estate-2026-09-21.json` (branch
   `task-glm-review-2026-10-14`) is the px-hashed snapshot of the
   operator's 09-21 EmailBison export; its provenance fixes the Signature
   column's first `<p>` as the owner and records display names separately
   as a non-authority.

A mailbox is ALLOWED when its owner group carries one of the committed
attestations and is not one of the three fictitious names. The attested
member binds the group because px equality is exactly NFC string equality
(operator decision 2026-10-15): every mailbox in the group carries the
identical signature owner name, and the estate's owner names partition it
into one human per name under the operator's declaration. Two committed
facts independently corroborate the binding: bernarda's group holds BOTH
of her attested mailboxes, and the five display-misspelled mailboxes
(2910, 3425, 3426, 3430, 3435 — display spelled without one `i`) all sit
inside kresimir's group with correct signatures
(`resonate-ops/glm-review-2026-10-14/b7_data_defects.md`).

The bound this method cannot break: an owner name not among the three
fictitious ones is treated as real only when a committed attestation ties
it to a roster human. The 2026-09-21 12:02Z census counted estate humans
by provider seat and got twelve identities for the same estate — including
one one-letter display variant — so outside the four bound groups,
name-to-human is NOT decidable from committed data, and those mailboxes
are UNDECIDED, not allowed. The census also floated 3735, 3736 and 3737 as
"best unattested mailbox per NEW human" attestation candidates before the
fictitious declaration existed; in this fixture they carry the Casey
Wright, Morgan Ellis and Riley Parker signatures. That is the concrete
demonstration of why canary selection goes through the owner list, never
the mailbox list.

## THE ALLOWLIST — 148 mailboxes, 4 owners

The canary rule (`resonate-ops/CANARY-01.md`) is one real owner, mailboxes
from the better-performing group, every attached sender sharing that one
owner and the copy signed with the owner's name. Pick ONE owner row below.

**kresimir — owner px-387dd1f77205 — 71 mailboxes**
(attested: eb-2739)

    2739 2744 2747 2753 2755 2759 2762 2765 2768 2771 2774 2777 2780 2781
    2910 3386 3388 3391 3392 3393 3395 3396 3397 3398 3399 3400 3401 3403
    3405 3407 3409 3410 3412 3413 3414 3416 3417 3418 3420 3422 3424 3425
    3426 3430 3435 3738 3741 3742 3744 3746 3748 3751 3753 3755 3756 3759
    3760 3763 3765 3766 3927 3928 3929 3930 3931 3932 3933 3934 3935 3936
    3937

    2910 3425 3426 3430 3435  display name misspelled, signature correct
    3760                      bounce-held 2026-09-21 at 2.29% (2% hard stop)

**bernarda — owner px-19834114d0e7 — 58 mailboxes**
(attested twice: eb-2737, eb-2740 — one human, two inboxes, per the operator)

    2737 2740 2743 2746 2749 2752 2754 2756 2758 2761 2764 2767 2770 2773
    2779 2905 2907 2914 3387 3389 3390 3394 3402 3404 3406 3408 3411 3415
    3419 3421 3423 3431 3739 3740 3743 3745 3747 3749 3750 3752 3754 3757
    3758 3761 3762 3764 3767 3938 3939 3940 3941 3942 3943 3944 3945 3946
    3947 3948

    3743 2.08%   3761 3.53%   3947 2.68%   bounce-held 2026-09-21

**ivan — owner px-75ee916b9999 — 13 mailboxes**
(attested: eb-2738)

    2738 2741 2745 2748 2750 2751 2757 2760 2763 2766 2772 2775 2778

**bojan — owner px-894888e9f1c3 — 6 mailboxes**
(attested: eb-2736)

    2736 2903 2904 2906 2911 3437

    3437                       bounce-held 2026-09-21 at 2.14%

The five bounce-held ids remain owner-allowed but measured above the 2%
hard stop on 2026-09-21; "better-performing group" selection should avoid
them until re-measured.

## THE COMPLEMENT — 53 mailboxes EXCLUDED

**Fictitious owner — 51.** Operator-declared fictitious people; excluded
by the 2026-09-21 Batch-1 condition and the 2026-10-14 confirmation.
Sequential id runs: these mailboxes were added as a block.

    Casey Wright  px-7513d195dfb1
    3687 3690 3693 3696 3699 3702 3705 3708 3711 3714 3717 3720 3723 3726
    3729 3732 3735

    Morgan Ellis  px-c82dcaabaec1
    3688 3691 3694 3697 3700 3703 3706 3709 3712 3716 3718 3721 3724 3727
    3730 3733 3736

    Riley Parker  px-494dc227d91e
    3689 3692 3695 3698 3701 3704 3707 3710 3713 3715 3719 3722 3725 3728
    3731 3734 3737

**No owner — 2.** Empty Signature; the owner authority is the signature,
and display names are explicitly not ownership evidence.

    2742 2782

**Owner unverifiable from export — 0.** No damaged rows in this export;
the fixture's damaged flag exists so a future mangled export classifies
itself.

## UNDECIDED — 24 mailboxes, and the canary treats them as EXCLUDED

Named owners, not fictitious, but no committed attestation binds the group
to a roster human. The remaining attested humans are fran, tomislav,
jakov and luka (committed in the 09-21 night handoff); which signature
names are theirs is not committed anywhere this repository can read, and
the 12:02Z census's seat-based human count (twelve identities, including
a one-letter variant) shows name-to-human is not 1:1 in the provider's
own data.

    px-898fe4fd21fe  12 mailboxes
    2776 3916 3917 3918 3919 3920 3921 3922 3923 3924 3925 3926

    px-a0e6d43e8d90  11 mailboxes
    2908 2909 2912 2913 3427 3428 3429 3432 3433 3434 3436

    px-523053400694  1 mailbox
    2769

    2742 2782 also border this list: their display names suggest a real
    team member ("jakov has two attested mailboxes", 09-22 morning
    handoff), but with an empty signature the fixture's owner authority
    says no owner, so they are EXCLUDED above. If the operator's
    attestations cover them, that is a decision, not an inference.

The authority that settles all of this: the `ownership_attestation` rows
in `work/senders.jsonl` (production state, gitignored — real names live
there and only there) and the sender bindings of campaigns 491–498, read
back by the operator or by a task explicitly authorised to read them.
Batch-1's own check text asserts the attested set was already 159 on
09-21, so most of these 24 are probably attested in production — but
probably is not a pass, and none of them is on the allowlist.

## The fixture is 24 days stale — membership is necessary, not sufficient

This allowlist is measured against the committed 2026-09-21 fixture: 225
mailboxes, 10 owner names. The estate on 2026-10-14 held **181 mailboxes
under 11 owner names** (`resonate-ops/CANARY-01.md`): 44 mailboxes have
left since the fixture was taken and one owner name differs. That current
export is production state and is not committed.

Therefore, at canary-attach time, every mailbox must pass BOTH gates:

1. its id is on the allowlist above (this document), AND
2. it is present in the current estate — verified against a fresh
   `scripts/email_sender_estate.py` readback (the sanctioned
   id-to-address printer), or a fixture regenerated by
   `resonate-ops/glm-review-2026-10-14/b7_make_estate_fixture.py` after a
   live read is authorised.

Any current-estate mailbox absent from this fixture is UNDECIDED-by-absence
and excluded. A stale allowlist entry that no longer exists is inert, not
a pass.
