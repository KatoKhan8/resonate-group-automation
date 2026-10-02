"""Which provider campaigns the operator has DECLARED to be Resonate OS.

WHY THIS IS A SEPARATE MODULE. `providerwrites.classify_campaign` already
answers ownership from the ledger, and for campaigns this code created that is
the whole answer. This module covers only the gap the ledger cannot reach:
`work/campaigns.jsonl` begins 2026-09-02, so a campaign created before that
has no canonical row, and the provider cannot be asked who owns it -
EmailBison's campaign record carries no owner, creator, user, team or tenant
field, confirmed across all 29 listing keys on 2026-09-28.

WHAT IT IS FOR, AND WHAT IT IS NOT FOR. It decides ATTRIBUTION: does a send
observed at the provider count as ours. That feeds the `legacy_touched` flag
and keeps the response rate of genuinely fresh leads separate from leads we
have written to before. It decides NOTHING about whether a lead may be
contacted. Under the operator's rule of 2026-10-02 the only blocking signal is
a REPLY; membership in an old, paused or HeyReach campaign blocks nothing.

THREE STATES, NOT TWO. `attribution()` returns `OURS`, `NOT_OURS` or
`UNKNOWN`. A campaign that is neither in the ledger nor declared is UNKNOWN,
and under invariant 0 an UNKNOWN never becomes either of the other two. A
caller that collapses UNKNOWN into OURS overstates our activity; one that
collapses it into NOT_OURS hides it. Both are wrong, so the type refuses to
let a caller do either by accident: there is no boolean on this surface.

THE FILE IS READ ON EVERY CALL, WITH NO CACHE. The operator edits it while
loops are running, and a cached list is a list that silently lags an operator
decision. Measured cost: the file is tens of lines.
"""
import os

from src import store

#: Returned when the operator has declared the campaign ours.
OURS = "ours"
#: Returned when the campaign is positively known to be somebody else's.
NOT_OURS = "not_ours"
#: Returned when neither authority can say. Never becomes OURS or NOT_OURS.
UNKNOWN = "unknown"

#: Env override, so a test can point at its own file without touching config/.
ENV_PATH = "RESONATE_OS_CAMPAIGNS"

PROVIDERS = ("bison", "heyreach")


def path():
    """Where the declarations live. Beside `config/`, overridable for tests."""
    return os.path.abspath(
        os.environ.get(ENV_PATH)
        or os.path.join(store.ROOT, "config", "resonate-os-campaigns.txt"))


class MalformedDeclaration(ValueError):
    """A line in the declaration file could not be read.

    Raised rather than skipped. A line the operator wrote and this code
    silently ignored is the worst outcome available: the operator believes a
    campaign is declared and it is not.
    """


def declared(file_path=None):
    """The declared set, as `{(provider, campaign_id)}`. Read fresh.

    A missing file is an EMPTY declaration, not an error - that is the state
    before the operator has marked anything, and it is honest. A file that
    exists but holds an unreadable line IS an error.
    """
    file_path = file_path or path()
    out = set()
    if not os.path.isfile(file_path):
        return out
    with open(file_path, encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                raise MalformedDeclaration(
                    "%s:%d expects '<provider> <campaign id>', got %r"
                    % (file_path, number, line))
            provider, campaign = parts[0].lower(), parts[1]
            if provider not in PROVIDERS:
                raise MalformedDeclaration(
                    "%s:%d provider must be one of %s, got %r"
                    % (file_path, number, ", ".join(PROVIDERS), provider))
            if not campaign.isdigit():
                raise MalformedDeclaration(
                    "%s:%d campaign id must be the PROVIDER's number, not a "
                    "canonical row id, got %r" % (file_path, number, campaign))
            out.add((provider, campaign))
    return out


def attribution(provider, campaign_id, ledger_says=None, file_path=None):
    """`OURS` / `NOT_OURS` / `UNKNOWN` for one provider campaign.

    `ledger_says` is what the ledger authority already concluded, if it was
    asked: `"resonate_os"` means the ledger claims it, and that wins without
    any declaration. Pass None when the ledger was not consulted or could not
    answer - and note that "could not answer" is NOT the same as "no", which is
    why this parameter is three-valued too.
    """
    if provider is None or campaign_id is None:
        return UNKNOWN
    provider = str(provider).lower()
    if provider not in PROVIDERS:
        return UNKNOWN
    if ledger_says == "resonate_os":
        return OURS
    if (provider, str(campaign_id)) in declared(file_path):
        return OURS
    if ledger_says == "resonate_internal":
        return NOT_OURS
    return UNKNOWN
