#!/usr/bin/env python3
"""GATE 2. Whose product is this copy about, and whose name signs it.

    from src import copyprovenance

    stamp = copyprovenance.certify(steps, client="productive",
                                   owner_name="Dana Whitfield")
    ...                                       # stamp rides in the lead's
                                              # custom variables
    report = copyprovenance.check_lead(lead_variables, owner_name="...",
                                       client="productive")

Operator's standing directive, 2026-09-25, written the afternoon 64 emails
carrying Resonate's own agency pitch went out of Productive's mailboxes
signed with the operator's name.

## THE THREE QUESTIONS, AND WHY EXISTING GATES ANSWER NONE OF THEM

`src/copylint.py` has six rules. `src/lint.py` has greetings, length,
placeholders and banned phrases. `bisonfactory._certified_copy` proves a
human approved these exact words. Between them they never ask:

  1. WHERE DID THIS TEMPLATE COME FROM? Every step must be traceable to the
     client's own copy file and must CARRY that template id in the lead's
     custom variables, so the provider itself holds the answer. A step with
     no id is REFUSED. It is not excused for having nothing to check.
  2. WHOSE PRODUCT DOES IT DESCRIBE? A client campaign that says
     `Resonate`, `outbound`, `agency founders`, `I work with`, `we run`,
     `pipeline` or the operator's name is describing OUR business out of
     OUR client's inbox.
  3. WHO SIGNS IT? The signature must equal the mailbox owner's name from
     the sender pool. `"Zvonimir"` was a string literal in a scratch
     script, and it went out of 41 mailboxes belonging to 6 different
     people.

## THE ABSENT-FIELD TRAP, NAMED BECAUSE IT WAS SPRUNG AN HOUR AGO

Lane S shipped a gate asking "does this row carry a LinkedIn URL". It
passed 12,407 rows of 12,407, because the supplier had already put a
`www.linkedin.com` URL in every row before anybody looked. The gate was
measuring the supplier, not the discovery.

So `template_id` is not checked for being non-empty. It is checked for
being a member of the set `template_ids(config)` DERIVES FROM THE CLIENT'S
OWN COPY FILE, and a lead that carries no id at all fails rather than
passes. Absence is the commonest state - none of the 1,465 leads in the
estate carries one today - and it has to read as a refusal or the gate
reports the estate clean on its first run.

## WHAT IS CHECKED, AND AGAINST WHAT

Against the words THE PROVIDER HOLDS, never against our render. The push
that caused the incident never rendered anything we could have checked: it
POSTed string literals straight to `bison.create_lead`. A refuse-list run
over our own render would have passed, because our render was not involved.
`check_lead` takes the lead's custom variables as read back off the
provider, and `src/reviewfile.py` is what reads them back.

## CERTIFY, AND WHY THE STAMP IS A FINGERPRINT RATHER THAN A FLAG

`certify` runs all three questions and returns custom variables carrying
the template ids AND a fingerprint over the exact words. The transport
verifies the fingerprint covers what is in the payload
(`providers.refuse_uncertified_copy`), so a script that writes its own
`copy_certified` variable has to also produce a fingerprint over copy that
passed - which is the check itself. A boolean flag would have been a
boolean anybody could set.
"""
import hashlib
import re

#: THE REFUSE-LIST, AT PHRASE LEVEL. Operator's list of 2026-09-25,
#: implemented as phrases after it was MEASURED against the live estate.
#:
#: ## WHY NOT THE BARE WORDS
#:
#: The list as written is `Resonate`, `outbound`, `agency founders`,
#: `I work with`, `we run`, `pipeline`. Matched as bare terms against
#: campaign 491 it refuses 286 of 333 leads and catches the incident in
#: NONE of them, because Productive's own approved opener is
#:
#:     "<Name>, I work with Marketing & Advertising teams on profitability
#:      visible on Monday not two weeks late, and I do not know how
#:      <Company> handles it"
#:
#: A gate that refuses 86% of a client's approved copy and 0% of the thing
#: it was written for is not strict, it is broken, and it is the shape that
#: gets a lint switched off. `I work with` is a fragment of English. `I
#: work with agency founders` is our pitch.
#:
#: ## WHAT ACTUALLY SEPARATES THEM
#:
#: The full phrases, plus the operator's name, plus - the strongest single
#: discriminator and the only exact one - the SIGNATURE. Productive's
#: approved bodies end on a question and carry no sign-off at all, because
#: `sender.mode: client_rep` says the mailbox appends its own. The sixty-
#: four ended `Zvonimir`.
REFUSED_PHRASES = (
    "i work with agency founders",
    "we run the outbound side",
    "the outbound side end to end",
    "second source of new business",
    "agency founders",
    "resonate group",
)

#: REPORTED, NOT REFUSED. The operator's bare terms, kept because they are
#: worth a human's eye on a review file and are not worth stopping a batch
#: for on their own. `check_step` returns these under `advisories`, the
#: review file prints them, and the audit counts them in a SEPARATE column
#: from the refusals - "matched a broad word" and "is the incident copy"
#: are different numbers and only the second one means anything.
BROAD_TERMS = (
    "resonate", "outbound", "i work with", "we run", "pipeline",
)

#: The operator's name, refused in client copy for the reason the list
#: above exists. A CONSTANT rather than a lookup: `sender_identity` reads
#: the CLIENT's representative, and the person whose name must never appear
#: is the one running the machine.
OPERATOR_NAMES = ("zvonimir",)

#: The custom variable that carries a step's template id at the provider.
#: Numbered by position, exactly as `subject_N` / `body_N` are, because a
#: five-step lead has five templates and one variable holds one value.
TEMPLATE_VARIABLE = "template_%d"

#: The fingerprint over the certified words, and the client it was certified
#: for. Both travel with the lead so the provider holds the evidence.
CERTIFICATE_VARIABLE = "copy_certificate"
CERTIFIED_FOR_VARIABLE = "copy_certified_for"

#: The mailbox owner the copy was certified against. A signature is checked
#: against the sender pool at certification time; this records WHICH owner,
#: so a lead moved to another mailbox afterwards stops matching.
CERTIFIED_OWNER_VARIABLE = "copy_certified_owner"

_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
_TAG = re.compile(r"<[^>]+>")

#: A MERGE FIELD THAT NEVER RESOLVED. `{BODY_3}` reaching a rendered step
#: means the lead carries no `body_3`: the provider holds the template and
#: nothing to put in it, so the prospect receives the literal string or an
#: empty message. Measured on campaign 491, where 94 of 333 leads render a
#: step this way today.
#:
#: It is ALSO why `signature_of` has to know about them. The last line of
#: `<p>{BODY_3}</p>` is a single capitalised token with no terminal
#: punctuation, which is precisely the shape of a signature - so the audit
#: reported `{BODY_3}` as a name signing 94 emails out of two people's
#: mailboxes before this was added.
UNRESOLVED_MERGE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


class CopyRefused(ValueError):
    """These words may not be staged for this client from this mailbox."""


def plain(html_or_text):
    """The words a person will read, with the provider's markup removed.

    `<br>` and `</p>` become newlines FIRST, because the provider stores
    `<p>...<br><br>Zvonimir</p>` and a naive tag strip runs the signature
    onto the end of the last sentence - which is exactly where the
    signature check would then fail to find it.
    """
    text = str(html_or_text or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)<p[^>]*>", "", text)
    text = _TAG.sub(" ", text)
    for entity, char in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                         ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(entity, char)
    return text


def template_ids(config, client=None):
    """Every template id THIS CLIENT'S COPY FILE authorises. A frozenset.

    DERIVED, NEVER LISTED. The client file names a cadence; `cadence
    .steps_for` resolves it to steps; each step's id is
    `<client>:<cadence>:<step key>` and, where the step names a template
    from `cadence.TEMPLATES`, `<client>:<cadence>:<step key>:<template>`.

    So the set moves when `productive.yaml` moves, and a step that is not in
    the client's cadence cannot be given an id that is in the set. A scratch
    script cannot mint one without reading the client's file, and if it
    reads the client's file it is using the client's copy.

    An empty set is returned for a config that names no cadence, and
    `check_lead` refuses every step against an empty set rather than
    passing them all - the direction that matters.
    """
    from . import cadence as _cadence

    config = config or {}
    name = str(config.get("cadence") or "").strip()
    if not name:
        return frozenset()
    client = str(client or config.get("name") or "").strip().lower()
    out = set()
    try:
        steps = _cadence.steps_for(config=config)
    except Exception:
        # A cadence that will not resolve authorises nothing. It does not
        # authorise everything, which is what an exception escaping here
        # would eventually be caught into.
        return frozenset()
    for step in steps or ():
        key = step.get("key")
        if not key:
            continue
        out.add("%s:%s:%s" % (client, name, key))
        template = step.get("template")
        if template:
            out.add("%s:%s:%s:%s" % (client, name, key, template))
        for entry in step.get(_cadence.VARIANTS_KEY) or ():
            variant = (entry or {}).get("variant_id") if isinstance(entry, dict) else None
            if variant:
                out.add("%s:%s:%s:%s" % (client, name, key, variant))
    return frozenset(out)


def _matches(text, terms):
    """Which of `terms` this copy carries. Lower-cased, in list order.

    Matched on WORD BOUNDARIES so `outbound` fires and `outbounds` in a
    quoted pack fact does not become a different string that slips past -
    and so `we run` does not fire inside `we running`, which is not English
    anyway but is the kind of thing a regex without boundaries invents.
    Whitespace is collapsed first, so a phrase still matches across the
    line break the provider put in the middle of it.
    """
    body = " %s " % re.sub(r"\s+", " ", plain(text)).lower()
    return [t for t in terms
            if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(t), body)]


def refused_phrases_in(text, extra=()):
    """The phrases that REFUSE this copy: our pitch, or the operator's name."""
    return _matches(text, tuple(REFUSED_PHRASES) + tuple(OPERATOR_NAMES)
                    + tuple(extra))


def broad_terms_in(text):
    """The operator's bare terms. Reported to a person, never a refusal."""
    return _matches(text, BROAD_TERMS)


def renders_to_nothing(subject, body, first_step=True):
    """Why this step would reach a prospect blank, or None.

    THE FAILURE THAT ACTUALLY REACHED THE MOST PEOPLE. 76 emails with an
    empty subject and a `<p></p>` body were SENT from campaigns 491-498 on
    2026-09-23, and 102 more are queued. The wrong-copy incident reached
    64. Blank is the bigger number and the simpler check.

    It is asked of the PROVIDER'S RENDERED OUTPUT, not of our variables
    dict. 491-498's sequence steps are `{SUBJECT_1}` and `<p>{BODY_1}</p>`,
    so a lead with no `body_1` produces a campaign, a schedule, a sender
    and a membership that all read correctly - and the provider renders the
    absent variable to nothing and sends the shell rather than refusing.
    Only the rendered row shows it.

    `first_step` because a threaded follow-up legitimately carries no
    subject of its own: `productive.yaml` gives every step
    `Re: {SUBJECT_1}` and the provider prepends `Re:` itself.
    """
    words = plain(body).strip()
    if not words:
        return "the body renders to nothing: this lead sends a blank email"
    if UNRESOLVED_MERGE.search(words):
        return ("the body still holds %s: the lead carries no value for it "
                "and the provider renders that to nothing"
                % ", ".join(sorted(set(UNRESOLVED_MERGE.findall(words)))))
    if first_step and not plain(subject).strip():
        return "the subject renders to nothing on the opening step"
    return None


def signature_of(body):
    """The name signing this message, or None.

    THE LAST NON-EMPTY LINE, and only when it looks like a name rather than
    a sentence: at most four words, no terminal punctuation, no question
    mark, and capitalised. `sender.mode: client_rep` in `productive.yaml`
    means the ENGINE writes no signature and the sending mailbox appends
    its own, so None is a legitimate and common answer - it is not a
    failure, and `check_step` treats it as one only when a signature was
    expected.
    """
    lines = [l.strip() for l in plain(body).splitlines() if l.strip()]
    if not lines:
        return None
    last = lines[-1]
    if last[-1] in ".!?,:;":
        return None
    if UNRESOLVED_MERGE.search(last):
        return None
    words = _WORD.findall(last)
    if not words or len(words) > 4 or len(words) != len(last.split()):
        return None
    if not all(w[:1].isupper() for w in words):
        return None
    return last


def _norm_name(value):
    return " ".join(_WORD.findall(str(value or "").lower()))


def check_step(text, *, template_id, owner_name, approved_ids,
               subject=None, expect_signature=None, first_step=True):
    """Verdict on ONE rendered step, as the provider holds it.

    `{ok, reasons, advisories, blank, template_id, signature}`.

    `reasons` REFUSE. `advisories` are for a person reading the review
    file and never change `ok` - see `BROAD_TERMS` for why that split
    exists and what it cost to learn.

    `expect_signature` is tri-state on purpose: True requires one and
    requires it to be the owner's, None accepts an absent signature (the
    `client_rep` mode where the mailbox appends it) but still refuses a
    WRONG one, and False refuses any signature at all.
    """
    reasons = []
    whole = " ".join([str(subject or ""), plain(text)])

    # 0. DOES IT RENDER AT ALL? First, because a blank step makes every
    #    other question moot and because blank is what reached 76 people.
    blank = renders_to_nothing(subject, text, first_step=first_step)
    if blank:
        reasons.append(blank)

    # 1. PROVENANCE. Absent is a refusal, not an excuse.
    tid = str(template_id or "").strip()
    if not tid:
        reasons.append(
            "no template id in the lead's custom variables: this step cannot "
            "say which line of the client's copy file it came from")
    elif tid not in approved_ids:
        reasons.append(
            "template id %r is not one the client's copy file declares "
            "(%d declared)" % (tid, len(approved_ids)))

    # 2. WHOSE PRODUCT. Against the provider's stored words, at phrase
    #    level. The bare terms are reported below and refuse nothing.
    hits = refused_phrases_in(whole)
    if hits:
        reasons.append("this is our pitch, not the client's: %s"
                       % ", ".join(repr(h) for h in hits))
    advisories = []
    for term in broad_terms_in(whole):
        if not any(term in h for h in hits):
            advisories.append(
                "broad term %r - ordinary English in the client's own "
                "approved copy; read the step" % term)

    # 3. WHO SIGNS IT.
    signature = signature_of(text)
    if signature is None:
        if expect_signature is True:
            reasons.append("no signature, and this client's copy signs every "
                           "step")
    elif expect_signature is False:
        reasons.append("signed %r, and this client's mailbox appends its own "
                       "signature" % signature)
    elif not _norm_name(owner_name):
        reasons.append(
            "signed %r and the mailbox owner is not known: a signature that "
            "cannot be compared to an owner is the constant that shipped"
            % signature)
    elif _norm_name(signature) != _norm_name(owner_name):
        reasons.append("signed %r and the mailbox belongs to %r"
                       % (signature, owner_name))

    return {"ok": not reasons, "reasons": reasons, "advisories": advisories,
            "blank": bool(blank), "incident": bool(hits),
            "template_id": tid or None, "signature": signature}


def variables_of(lead_or_mapping):
    """Custom variables as a mapping, from either wire shape."""
    if isinstance(lead_or_mapping, dict) and "custom_variables" in lead_or_mapping:
        return {v.get("name"): v.get("value")
                for v in lead_or_mapping.get("custom_variables") or []
                if isinstance(v, dict)}
    return dict(lead_or_mapping or {})


def steps_in(variables):
    """`[(position, subject, body)]` for every numbered step a lead carries.

    The unnumbered single-step shape (`subject`/`body`) is position 1, which
    is what campaign 451 is staged against.
    """
    variables = variables or {}
    positions = sorted(
        int(m.group(1)) for m in
        (re.fullmatch(r"body_(\d+)", str(k) or "") for k in variables)
        if m)
    if positions:
        return [(n, variables.get("subject_%d" % n),
                 variables.get("body_%d" % n)) for n in positions]
    if variables.get("body") or variables.get("subject"):
        return [(1, variables.get("subject"), variables.get("body"))]
    return []


def check_lead(lead, *, owner_name, config=None, client=None,
               approved_ids=None, expect_signature=None):
    """Every step of one lead, as the provider holds it.

    `{ok, steps: [...], reasons: [...]}`. A lead with NO steps is refused:
    a staged lead whose copy variables are absent renders as an empty email
    and one was measured on campaign 491 - 46 of 333 leads carry an empty
    `body_1` today.
    """
    variables = variables_of(lead)
    if approved_ids is None:
        approved_ids = template_ids(config, client)
    steps = steps_in(variables)
    out = {"ok": True, "steps": [], "reasons": [], "advisories": [],
           "blank": False, "incident": False}
    if not steps:
        out["ok"] = False
        out["blank"] = True
        out["reasons"].append(
            "the lead carries no copy variables at all: every step of this "
            "campaign's sequence is a merge field, so the provider renders "
            "nothing and sends the shell")
        return out
    for position, subject, body in steps:
        verdict = check_step(
            body, template_id=variables.get(TEMPLATE_VARIABLE % position),
            owner_name=owner_name, approved_ids=approved_ids,
            subject=subject, expect_signature=expect_signature,
            first_step=(position == 1))
        verdict["position"] = position
        out["steps"].append(verdict)
        out["advisories"] += verdict["advisories"]
        out["blank"] = out["blank"] or verdict["blank"]
        out["incident"] = out["incident"] or verdict["incident"]
        if not verdict["ok"]:
            out["ok"] = False
    return out


def constant_signatures(pairs):
    """Signatures used across MORE THAN ONE mailbox owner. The batch rule.

    `pairs` is `[(signature, owner_name)]`. The per-step check already
    refuses a signature that does not match its own mailbox, and this
    catches the shape that made the incident big rather than small: ONE
    literal, 41 mailboxes, 6 real people. A batch where every lead is
    signed identically is a batch where nobody asked who owned the inbox,
    and that is visible only across the batch.
    """
    owners = {}
    for signature, owner in pairs or ():
        if not signature:
            continue
        owners.setdefault(_norm_name(signature), set()).add(_norm_name(owner))
    return {sig: sorted(o for o in who if o)
            for sig, who in owners.items() if len(who) > 1}


# ------------------------------------------------------------ certification

def _material(steps, client, owner_name):
    """Exactly the bytes a certificate covers. Order is part of it."""
    parts = [str(client or "").lower(), _norm_name(owner_name)]
    for position, template_id, subject, body in steps:
        parts += [str(position), str(template_id or ""),
                  str(subject or ""), str(body or "")]
    return "\x1f".join(parts)


def certificate(steps, client, owner_name):
    """The fingerprint over these words, this client and this mailbox owner."""
    return hashlib.sha256(
        _material(steps, client, owner_name).encode("utf-8")).hexdigest()[:32]


def certify(steps, *, client, owner_name, config=None, approved_ids=None,
            expect_signature=None):
    """Run all three questions and return the custom variables to stage.

    `steps` is `[(position, template_id, subject, body)]`.

    RAISES on refusal rather than returning a verdict, because this is the
    minting function: a caller that wanted a report should call
    `check_lead`. The only way to obtain a certificate is to hand in copy
    that passes, which is what makes the certificate proof of anything.
    """
    if approved_ids is None:
        approved_ids = template_ids(config, client)
    steps = list(steps or ())
    if not steps:
        raise CopyRefused("nothing to certify: no steps")
    problems = []
    for position, template_id, subject, body in steps:
        verdict = check_step(body, template_id=template_id,
                             owner_name=owner_name, approved_ids=approved_ids,
                             subject=subject,
                             expect_signature=expect_signature)
        for why in verdict["reasons"]:
            problems.append("step %s: %s" % (position, why))
    if problems:
        raise CopyRefused("; ".join(problems))
    values = {CERTIFICATE_VARIABLE: certificate(steps, client, owner_name),
              CERTIFIED_FOR_VARIABLE: str(client or "").lower(),
              CERTIFIED_OWNER_VARIABLE: str(owner_name or "")}
    for position, template_id, _subject, _body in steps:
        values[TEMPLATE_VARIABLE % int(position)] = str(template_id)
    return values


def verify_certificate(variables, *, client=None):
    """Does the certificate this lead carries cover the words it carries?

    Returns `(ok, why)`. Used by the TRANSPORT, which knows nothing about
    clients or cadences and does not need to: it only has to establish that
    something which DID know signed off on these exact bytes.
    """
    variables = variables_of(variables)
    held = str(variables.get(CERTIFICATE_VARIABLE) or "").strip()
    if not held:
        return False, ("the payload carries prospect-facing copy and no "
                       "`%s`: nothing certified these words"
                       % CERTIFICATE_VARIABLE)
    for_client = str(variables.get(CERTIFIED_FOR_VARIABLE) or "").strip().lower()
    if not for_client:
        return False, "the certificate names no client"
    if client and for_client != str(client).strip().lower():
        return False, ("the certificate was minted for %r and this write is "
                       "for %r" % (for_client, client))
    owner = variables.get(CERTIFIED_OWNER_VARIABLE)
    steps = [(position, variables.get(TEMPLATE_VARIABLE % position),
              subject, body)
             for position, subject, body in steps_in(variables)]
    if not steps:
        return False, "the certificate covers no steps"
    if certificate(steps, for_client, owner) != held:
        return False, ("the certificate does not cover the copy in this "
                       "payload: the words changed after they were certified")
    return True, "certified"
