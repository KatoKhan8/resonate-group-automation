#!/usr/bin/env python3
"""The per-seat daily ceiling for LinkedIn, from PROVIDER MEASUREMENT.

WHY THIS MODULE EXISTS. The three numbers an operator quotes - "40/40 is the
hard ceiling, HeyReach policy is 30, day one is 5" - were nowhere in the
code. `seatledger.LIMIT = 40` carried one of them as a bare literal with no
provenance, `pilotcaps` carried a `linkedin_per_day` of 10 that is an ESTATE
total rather than a per-seat figure, and no constant anywhere held 30 or 5.
Three numbers in an instruction and one unsourced literal in the code is how
a cap gets quietly disagreed with.

THE MEASUREMENT, and it is a measurement rather than a quote.

    $ python -c "... heyreach.all_li_accounts() ..."     2026-10-03
    TOTAL_SEATS 41 FETCHED 41
    MAXES [40]
    LIMITS [5, 10, 15, 17, 18, 19, 22, 23, 25, 40]
    AUTHVALID_TRUE 33 FALSE 8

`connectioRequestMax` - the provider's own plan ceiling, misspelled by
HeyReach and preserved verbatim - reads 40 on every one of the 41 seats.
That is the only one of the three numbers the provider actually states, and
it is the hard one. The configured `connectioRequestLimit` varies 5 to 40
across the estate and is a per-seat setting, not a policy.

WHAT THE PROVIDER DOES NOT SAY. There is no remaining-today counter anywhere
on the HeyReach seat object - checked across every numeric field on all 41
seats. So "today's spend" cannot be read back per seat, and this module will
not invent it: `headroom` returns UNKNOWN unless a caller supplies a measured
spend, and UNKNOWN is never silently treated as room.

THE THREE CEILINGS, AND WHY THE SMALLEST ALWAYS WINS. They are not
alternatives to choose between. The provider's 40 is what the account is
technically capable of; 30 is the policy HeyReach publishes for what a
profile may safely do; 5 is what the operator authorised for day one of a
pilot. A day-one run that took 30 because 30 is "the policy" would be
exceeding its authorisation, and one that took 40 because the provider
allows it would be doing both.
"""

#: HeyReach's own plan ceiling, read off `connectioRequestMax`. Measured
#: 2026-10-03: 40 on 41 of 41 seats, no exceptions.
PROVIDER_HARD_CEILING = 40

#: HeyReach's published guidance for a single profile. Not readable from the
#: API - it is policy, not configuration - so it is carried here as a named
#: constant rather than pretended to be a measurement.
PROVIDER_POLICY_CEILING = 30

#: Day one of the pilot, per the operator. The whole point of a pilot's first
#: day is that it is far below what is permitted.
PILOT_DAY_ONE = 5

#: The field names HeyReach uses, misspelling included. Preserved exactly:
#: "correcting" it in our code reads the wrong key and silently yields None,
#: which this module would then have to treat as unknown.
PROVIDER_MAX_FIELD = "connectioRequestMax"
PROVIDER_LIMIT_FIELD = "connectioRequestLimit"

#: Returned wherever the provider states nothing. Never 0, because 0 reads as
#: "no room" and this means "we did not ask or it did not say" - and never a
#: number, because a guessed headroom spends itself.
UNKNOWN = "unknown"

#: The cooldown flags on a seat. Any one of them true means the provider has
#: put that seat in a hold and it must not be given work today.
COOLDOWN_FIELDS = ("connectionRequestCooldown", "connectionNoteCooldown",
                   "inMailCooldown", "searchCooldown")


class SeatUnusable(Exception):
    """This seat may not be given work today. Carries the reason."""

    def __init__(self, seat_id, why):
        super().__init__(f"seat {seat_id}: {why}")
        self.seat_id = seat_id
        self.why = why


def in_cooldown(seat):
    """The cooldown flags that are set on this seat, as a sorted tuple."""
    return tuple(sorted(f for f in COOLDOWN_FIELDS if (seat or {}).get(f)))


def _limits_of(seat):
    """The limits sub-object, whatever HeyReach called it on this row.

    Located by looking for the misspelled key rather than by a fixed path:
    the route returns the seat untrimmed and the nesting has moved once
    already. A fixed path that stops matching returns None, and None here
    would read as "no configured limit", which is the loose direction.
    """
    for value in (seat or {}).values():
        if isinstance(value, dict) and PROVIDER_MAX_FIELD in value:
            return value
    return {}


def configured_limit(seat):
    """This seat's own configured daily connection-request limit, or UNKNOWN."""
    value = _limits_of(seat).get(PROVIDER_LIMIT_FIELD)
    return UNKNOWN if value is None else int(value)


def provider_max(seat):
    """The provider's stated hard ceiling for this seat, or UNKNOWN.

    Read from the seat rather than assumed to be `PROVIDER_HARD_CEILING`.
    The measurement says all 41 agree today; a seat that stops agreeing must
    be believed over the constant, which is why this reads the row.
    """
    value = _limits_of(seat).get(PROVIDER_MAX_FIELD)
    return UNKNOWN if value is None else int(value)


def require_usable(seat):
    """Raise `SeatUnusable` unless this seat may be given work today.

    The operator's rule: a seat in cooldown, or with `authIsValid` false,
    DROPS OUT - of the batch's seat list, not of the batch. A caller
    iterating seats catches this per seat and keeps going.
    """
    seat_id = (seat or {}).get("id")
    if not (seat or {}).get("authIsValid"):
        raise SeatUnusable(seat_id, "authIsValid is false: the profile's "
                                    "session is not valid, so nothing it is "
                                    "given today would send")
    if not (seat or {}).get("isActive"):
        raise SeatUnusable(seat_id, "the seat is not active")
    cooling = in_cooldown(seat)
    if cooling:
        raise SeatUnusable(
            seat_id, f"the provider has this seat in cooldown "
                     f"({', '.join(cooling)}); work given to a seat in "
                     f"cooldown is not sent, it is queued against a hold")
    return True


def day_one_cap(seat, spent_today=None):
    """How many connection requests this seat may be given on pilot day one.

    THE SMALLEST OF EVERY CEILING THAT APPLIES, and never above measured
    headroom. Returns an int, or raises `SeatUnusable`.

    `spent_today` is what the caller MEASURED at the provider. The provider
    publishes no remaining-today counter, so None means "not measured" and
    is handled the only safe way: the cap is computed as if the seat's whole
    allowance were still to be proven, which on day one is 5 regardless -
    but `headroom_is_known` reports False so a caller cannot present an
    unmeasured figure as a measured one.
    """
    require_usable(seat)
    ceilings = [PILOT_DAY_ONE, PROVIDER_POLICY_CEILING, PROVIDER_HARD_CEILING]
    stated_max = provider_max(seat)
    if stated_max != UNKNOWN:
        ceilings.append(stated_max)
    configured = configured_limit(seat)
    if configured != UNKNOWN:
        ceilings.append(configured)
    cap = min(ceilings)
    if spent_today is not None:
        cap = min(cap, max(0, int(stated_max if stated_max != UNKNOWN
                                  else PROVIDER_HARD_CEILING)
                           - int(spent_today)))
    return cap


def headroom_is_known(spent_today):
    """Did anybody actually measure what this seat has already spent today?

    Separate from `day_one_cap` on purpose. The cap is safe either way; the
    CLAIM "this seat has N left" is only safe when somebody measured, and a
    checkpoint that reports a computed cap as a measured headroom is the
    kind of thing that reads as evidence and is not.
    """
    return spent_today is not None


def allocate(seats, candidates, spent_by_seat=None, require_measured=True):
    """Distribute candidates across seats, most free headroom first.

    Returns `(assignment, dropped)` where assignment is
    `{seat_id: [candidate, ...]}` and dropped is `[(seat_id, why), ...]`.

    A seat that drops out takes no candidates and does not stop the batch.
    Candidates that do not fit are returned unassigned by the caller's own
    arithmetic - this never silently discards one, and never exceeds a cap
    to make the numbers come out.

    `require_measured=True` IS INVARIANT 0 APPLIED TO HEADROOM, and it is the
    default because the safe value has to be the one you get by not thinking
    about it. A seat whose spend today was not measured is UNKNOWN, and
    UNKNOWN is not a pass, not zero, and not idle. It drops out exactly as a
    seat in cooldown does.

    WHY THIS IS NOT THEORETICAL HERE. Verified against the live estate
    2026-10-03: the HeyReach seat object carries 24 fields and every numeric
    one is a LIMIT or a MAX (`connectioRequestLimit/Max`, `messageLimit/Max`,
    `inMailLimit/Max`, `followLimit/Max`, `profileViewLimit/Max`,
    `postLikeLimit/Max`). There is no used-today, remaining-today or
    sent-today counter on any route. So today's spend must be DERIVED, and
    the only available derivation - counting conversations whose
    `lastMessageAt` is today, per seat, through the inbox filter - counts
    MESSAGES. A connection request that has not been accepted yet produces
    no conversation at all, so the derivation cannot see the very quantity
    this cap governs, and its undercount has no upper bound: a seat showing
    zero conversations today may have spent its whole allowance on pending
    requests.

    An undercount is only safe for a cap if it is treated as a floor on what
    was spent - assume MORE went out than you can see. With no bound on the
    gap, that assumption yields no provable headroom, which is why the
    default here refuses rather than spreads.
    """
    spent_by_seat = spent_by_seat or {}
    usable, dropped = [], []
    for seat in seats or []:
        seat_id = (seat or {}).get("id")
        spent = spent_by_seat.get(str(seat_id))
        if require_measured and not headroom_is_known(spent):
            dropped.append((
                seat_id,
                "today's spend at the provider is UNKNOWN: HeyReach "
                "publishes no used-today counter and the inbox derivation "
                "cannot see unaccepted connection requests, so no headroom "
                "is provable. UNKNOWN is not headroom"))
            continue
        try:
            cap = day_one_cap(seat, spent)
        except SeatUnusable as exc:
            dropped.append((seat_id, exc.why))
            continue
        if cap > 0:
            usable.append((seat_id, cap))
    # Most free headroom first, then by seat id so the result is stable and
    # a re-run assigns the same people to the same humans.
    usable.sort(key=lambda pair: (-pair[1], str(pair[0])))
    assignment = {seat_id: [] for seat_id, _cap in usable}
    caps = dict(usable)
    queue = list(candidates or [])
    # Round-robin rather than filling one seat to its cap and moving on: 20
    # requests from one profile and nothing from eleven others is the
    # footprint of a tool, which is the thing a per-seat cap exists to avoid.
    progressed = True
    while queue and progressed:
        progressed = False
        for seat_id, _cap in usable:
            if not queue:
                break
            if len(assignment[seat_id]) < caps[seat_id]:
                assignment[seat_id].append(queue.pop(0))
                progressed = True
    return assignment, dropped
