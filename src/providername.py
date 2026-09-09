#!/usr/bin/env python3
"""What a Resonate campaign should be called inside a provider.

## Why this exists as a name and not as a call

Resonate does not create provider campaigns. `src/providers/bison.py` and
`heyreach.py` expose lead-adding endpoints and nothing else, and creating
a campaign is a mutation this build does not perform. So today an operator
creates the campaign by hand in EmailBison or HeyReach and pastes its id
into the settings screen.

That is exactly why the name matters. An employee opening EmailBison sees
a list of campaigns somebody typed, and there is nothing on the screen to
say which of them Resonate is filling. This produces the string to give
them, so the answer is legible from inside the provider.

When campaign creation does exist, `render()` is the call site. Until
then it is what the mapping screen tells an operator to type.

## The marker is unambiguous on purpose

`[RESONATE-AUTO]` rather than `[AUTO]`. A provider account may hold
automation from several tools, and `[AUTO]` answers "something automated
this" without answering "what". The point of the marker is to identify
the owner, so it names it.

## A name is a label, never an identity

Nothing in this system may match a provider campaign by its name.
Provider ids are stored per provider on the campaign record, and they are
what a payload is addressed to. Somebody renaming a campaign inside
EmailBison breaks nothing here, which is the property this module must not
quietly cost - so it exports no lookup, no parse-back, and no reverse
mapping. Rendering is one-way.

## Metadata is proposed, not assumed

`metadata()` returns the fields that *would* mark ownership machine-
readably. Whether either provider accepts custom fields on a campaign is
not established in this build:

    LIVE CONTRACT VALIDATION REQUIRED

Nothing sends them. They are returned so the shape is agreed and so the
mapping screen can show what would be attached.
"""
import re

# The marker. Not `[AUTO]`: a provider account can hold automation from
# several tools, and the question an employee has is whose.
MARKER = "[RESONATE-AUTO]"

SEPARATOR = " | "

EMAIL = "EMAIL"
LINKEDIN = "LINKEDIN"
CHANNELS = (EMAIL, LINKEDIN)

# Providers truncate, and a name cut off mid-identifier is worse than a
# short one: the campaign id is the part somebody needs to match against
# Resonate, and it is last. When the whole name will not fit, the segment
# that gets dropped is the descriptive one, never the marker and never the
# id.
MAX_LENGTH = 255


def _clean(value):
    """One segment, safe inside a provider's name field.

    The separator is stripped rather than escaped: a pipe inside a segment
    would make the rendered name ambiguous to read, and legibility is the
    entire point of this string.
    """
    text = re.sub(r"[|\r\n\t]+", " ", str(value or "")).strip()
    return re.sub(r"\s{2,}", " ", text)


def render(workspace, channel, campaign_id, segment=None, playbook=None,
           maximum=MAX_LENGTH):
    """The name to give the provider campaign.

        [RESONATE-AUTO] | Productive | EMAIL | DACH Agencies 50-100 | C-0241

    `segment` and `playbook` are both optional and the first present one is
    used - they answer the same question for a reader ("which approach is
    this") and printing both makes the name longer without making it
    clearer.
    """
    channel = (channel or "").upper()
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel: {channel!r}")
    if not campaign_id:
        raise ValueError("a provider campaign name must carry the campaign id")

    describes = _clean(segment or playbook or "")
    parts = [MARKER, _clean(workspace), channel]
    if describes:
        parts.append(describes)
    parts.append(_clean(campaign_id))

    name = SEPARATOR.join(p for p in parts if p)
    if len(name) <= maximum:
        return name

    # Too long. Drop the description first, then trim it, and never touch
    # the marker, the workspace, the channel or the id.
    fixed = SEPARATOR.join(
        [MARKER, _clean(workspace), channel, _clean(campaign_id)])
    if not describes or len(fixed) >= maximum:
        return fixed[:maximum]

    room = maximum - len(fixed) - len(SEPARATOR)
    if room <= 1:
        return fixed
    shortened = describes[:room - 1].rstrip() + "…"
    return SEPARATOR.join(
        [MARKER, _clean(workspace), channel, shortened, _clean(campaign_id)])


def metadata(workspace, campaign_id):
    """Machine-readable ownership, if a provider will hold it.

    Returned rather than sent. Whether EmailBison or HeyReach accepts
    custom fields on a campaign is not established here, and inventing a
    capability is how an integration ships broken:

        LIVE CONTRACT VALIDATION REQUIRED
    """
    return {
        "managed_by": "resonate",
        "automation": True,
        "resonate_campaign_id": campaign_id,
        "workspace_id": workspace,
    }


def is_managed(name):
    """Does this name claim Resonate ownership?

    For reading a provider's campaign list and telling an operator which
    rows are ours - a display question. It is deliberately not an identity
    lookup, and nothing in this system may route or match on the answer:
    a campaign renamed by hand inside the provider is still the same
    campaign, and its id still says so.
    """
    return str(name or "").strip().startswith(MARKER)


def describe(workspace, campaign_id, segment=None, playbook=None):
    """Both channel names and the metadata, for one campaign.

    One logical Resonate campaign maps to two provider campaigns, and
    both carry the same canonical id - which is what makes them findable
    as a pair from either side.
    """
    return {
        "campaign_id": campaign_id,
        "workspace": workspace,
        "names": {
            channel.lower(): render(workspace, channel, campaign_id,
                                    segment, playbook)
            for channel in CHANNELS
        },
        "metadata": metadata(workspace, campaign_id),
        "marker": MARKER,
        # Said where a reader of the value will see it, not only in a
        # document.
        "note": ("Resonate does not create provider campaigns in this "
                 "build. This is the name to give the campaign when you "
                 "create it, so it is recognisable from inside the "
                 "provider. Identity is the provider campaign id, never "
                 "this string."),
        "metadata_supported": None,
    }
