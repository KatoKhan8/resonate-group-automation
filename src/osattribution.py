"""Whether a provider campaign is Resonate OS, asked of the ONE authority.

THERE USED TO BE TWO ANSWERS TO THIS QUESTION AND THAT WAS THE DEFECT. This
module shipped with its own hand-maintained declaration file,
`config/resonate-os-campaigns.txt`, listing the campaigns the operator had
marked ours. `collision.os_campaign_ids` already answered the same question
from the canonical ledger, and the two could disagree - which means a lead's
attribution depended on which function a caller happened to reach for.

MEASURED 2026-10-02, AND IT IS WHY THE FILE IS GONE RATHER THAN RECONCILED.
The declaration file was a strict SUBSET of the authority on both channels:

    channel    authority    the file    authority-only    file-only
    bison             20           4                16            0
    heyreach          40          36                 4            0

A file-only column of zero on both rows is the whole argument. The file named
nothing the ledger did not already name, so deleting it loses no operator
decision - it only removes a second place to forget to update. The operator's
instruction of 2026-10-02: "OS autoritet: `os_campaign_ids()` je jedini."

TWO FUNCTIONS, NOT ONE, BECAUSE THERE ARE TWO CHANNELS. The authority is a
PAIR and both halves are needed:

    collision.os_campaign_ids()           -> (frozenset[int], readable)  BISON
    collision.our_heyreach_campaign_ids() -> (frozenset[str], readable)  HEYREACH

`os_campaign_ids` reads only `bison_campaign_id`, so it is silent about
LinkedIn - that is not a gap in it, it is the division of labour. Its HeyReach
sibling carries the stronger claim: a HeyReach conversation row names no
campaign at all, so our own record of having staged the person is the ONLY way
LinkedIn ownership is knowable. Neither function is patched here; this module
asks the right one of the pair and reconciles their id types.

THE TWO ID TYPES ARE RECONCILED AT THIS BOUNDARY, ONCE. Bison ids arrive as
ints and HeyReach ids as strings, and a provider lead row may hand either one
back as the other. `_key` is the single place that settles it, so no call site
has to guess and no comparison depends on `481 == "481"` being false. See its
docstring for why a numeric id is compared as a number.

THREE STATES, NOT TWO. `attribution()` returns `OURS`, `NOT_OURS` or
`UNKNOWN`, and an UNKNOWN never becomes either of the other two. A caller that
collapses UNKNOWN into OURS overstates our activity; one that collapses it
into NOT_OURS hides a send we made. Both are wrong, so there is no boolean on
this surface for a caller to collapse it with by accident.

THE AUTHORITY IS ASKED ON EVERY CALL, WITH NO CACHE, for the reason the file
was read on every call: the ledger grows while loops are running, and a cached
set is a set that silently lags. `campaigns.load()` is tens of kilobytes.
"""

#: Returned when the authority records the campaign as ours.
OURS = "ours"
#: Returned when the campaign is positively known to be somebody else's.
NOT_OURS = "not_ours"
#: Returned when the authority cannot say. Never becomes OURS or NOT_OURS.
UNKNOWN = "unknown"

PROVIDERS = ("bison", "heyreach")


def _key(value):
    """One comparable form for a provider campaign id, for both channels.

    THIS IS THE INT/STR RECONCILIATION, AND IT BELONGS HERE RATHER THAN AT THE
    CALL SITES. `os_campaign_ids` yields ints and `our_heyreach_campaign_ids`
    yields strings, while a provider lead row's `campaign_id` may be either.
    Comparing those raw makes `481 in {"481"}` false, which reads as "not ours"
    - the exact silent miss this module exists to prevent.

    A NUMERIC ID IS COMPARED AS A NUMBER, so `481`, `"481"`, `" 481 "` and
    `"0481"` are one campaign rather than four. Every id in both channels is
    numeric today - bison 451-506, heyreach 594061-621824 - but a non-numeric
    id is kept as its stripped text rather than refused, because an id this
    function cannot parse must not silently become None and read as absent.

    Returns None only for a genuinely absent id. A bool is not an id: `True`
    is `1` in Python and would otherwise alias campaign 1.
    """
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return str(int(text))
    except ValueError:
        return text


def authority(provider):
    """`(ids, readable)` for one channel, ids as comparable keys.

    The ONLY place either half of the authority pair is called. `readable` is
    passed through untouched and is load-bearing - see `attribution`.
    """
    # Lazy, as `collision` imports it of its own modules: this module is
    # destined for the eligibility path, and a top-level import of `collision`
    # would make that a cycle the moment eligibility is wired in.
    from src import collision

    provider = (str(provider) if provider is not None else "").lower()
    if provider == "bison":
        ids, readable = collision.os_campaign_ids()
    elif provider == "heyreach":
        ids, readable = collision.our_heyreach_campaign_ids()
    else:
        # Not a channel this system writes to. Nothing is knowable about it,
        # and "unreadable" is the honest word for that rather than "empty".
        return frozenset(), False
    return frozenset(k for k in (_key(i) for i in ids) if k is not None), \
        bool(readable)


def attribution(provider, campaign_id, ledger_says=None, authority_says=None):
    """`OURS` / `NOT_OURS` / `UNKNOWN` for one provider campaign.

    `ledger_says` is what `providerwrites.classify_campaign` already concluded
    if it was asked: `"resonate_os"` claims the campaign and wins outright,
    `"resonate_internal"` positively disowns it. Pass None when it was not
    consulted or could not answer - and note that "could not answer" is NOT
    "no", which is why this parameter is three-valued too.

    `authority_says` injects a pre-read `(ids, readable)` pair, for a caller
    that already has one and for tests. Omit it and the authority is asked.

    AN UNREADABLE AUTHORITY IS `UNKNOWN`, NEVER `NOT_OURS`, AND THAT IS THE
    LOAD-BEARING LINE IN THIS FUNCTION. `campaigns.load()` returns nothing both
    when we own no campaigns and when the file could not be read at all, and
    those two have opposite consequences. Empty-but-READ means no campaign is
    ours, which is correct and makes the lead cold. UNREADABLE collapsing to
    the same answer would mark every lead we have ever written to as never
    contacted, and hand a full new sequence to all of them - the failure
    `os_campaign_ids` carries its second return value to prevent. So the
    readable check sits ABOVE the `resonate_internal` arm: with the authority
    unreadable this function will not disown a campaign even on a positive
    internal claim, because the claim it cannot check is the membership that
    would have made it ours.

    The `resonate_os` arm sits above the check instead, because it can only
    make the verdict MORE conservative: concluding a campaign is ours marks
    the lead legacy_touched, which withholds outreach rather than spending it.
    """
    if provider is None or campaign_id is None:
        return UNKNOWN
    provider = str(provider).lower()
    if provider not in PROVIDERS:
        return UNKNOWN
    if ledger_says == "resonate_os":
        return OURS
    ids, readable = (authority(provider) if authority_says is None
                     else (frozenset(k for k in (_key(i)
                                                 for i in authority_says[0])
                                     if k is not None),
                           bool(authority_says[1])))
    if not readable:
        return UNKNOWN
    key = _key(campaign_id)
    if key is not None and key in ids:
        return OURS
    if ledger_says == "resonate_internal":
        return NOT_OURS
    return UNKNOWN
