#!/usr/bin/env python3
"""Compare the text the provider will actually SEND against the approved copy.

    py -3 scripts/queued_copy_readback.py 487
    py -3 scripts/queued_copy_readback.py 487 489

READ-ONLY. Provider GETs and canonical reads. Exits non-zero on any mismatch.

## The gap this closes

`bison_readback.py` compares the SEQUENCE - three steps, thread_reply, waits,
and subjects that read `{SUBJECT_1}` on both sides. It passes on 487 today and
it is right to. But every field it compares is a PLACEHOLDER, and the standing
correction says so in as many words: do not compare approved resolved copy
against provider placeholders while ignoring lead-level custom variables. A
sequence can be perfect and every rendered email wrong - a variable that
resolves empty, a name that never substituted, a body carrying another lead's
company - and nothing in the sequence readback can see it.

**The provider renders the queue before it sends it.** Each `scheduled_emails`
row carries `email_subject` and `email_body` fully resolved, for that lead,
with that lead's custom variables already substituted. That is the sendable
text, it is readable days ahead of the send, and until now nothing read it.

## What it compares

    provider row  ->  lead email  ->  canonical record + contact
                  ->  sequence_step_id -> step ordinal -> cadence key
                  ->  cadence[contact][key].subject / .body

The body transform has two halves and only one of them is ours. Paragraphs
joined by a blank line become `<br><br>` inside one `<p>` - that is the
factory, on write. **The HTML ENTITIES ARE THE PROVIDER'S, on render**, and
that was measured rather than assumed: three of 487's ten rows read
`Marketing &amp; Advertising` where the approved copy reads `Marketing &
Advertising`, and reading the lead's own `body_1` custom variable back showed
a bare `&` on our side. The provider escapes when it substitutes the variable
into the HTML step. The prospect sees `&`.

So both halves are undone before comparing, in that order - tags first, then
entities. Reversed, an escaped `&lt;br&gt;` in somebody's copy would become a
real line break and the check would approve markup nobody wrote. Undoing
rather than stripping, because stripping would also hide a stray tag, and a
stray tag in a prospect-facing email is exactly the defect worth catching.

Unescaping ONCE, and only the provider's side. Our stored copy is plain text.
A body the provider returns double-encoded (`&amp;amp;`) still fails, which
is right: that one really would reach a prospect reading `&amp;`.

## What a mismatch means

Not "regenerate". A queued row whose text is not the approved text is a
campaign that must not send, and the fix is upstream of this script. It exits
non-zero so it can gate.

## What it cannot prove

That the approved copy is GOOD, that the lead is the right person, or that
the address verifies. Other gates own those. This one answers a single
question - will the words that reach a real prospect be the words a human
approved - and it answers it against the provider's own render rather than
against our intention.
"""
import argparse
import html as html_module
import os
import re
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.bison_readback import _setup_data_access      # noqa: E402


def unwrap(html):
    """The plain text a prospect will read, from the provider's rendered HTML.

    Returns None if the shape is not the one the factory writes - None rather
    than a best effort, because a body this cannot account for is a body that
    did not come from our writer, and saying so is more useful than silently
    comparing something else.

    TAGS FIRST, THEN ENTITIES. `<br>` is real markup the factory wrote;
    `&amp;` is the provider escaping a variable's value on render. Reversed,
    an escaped `&lt;br&gt;` in somebody's copy would turn into a real line
    break and this would approve markup nobody wrote.
    """
    if html is None:
        return None
    text = str(html).strip()
    match = re.fullmatch(r"<p>(.*)</p>", text, flags=re.DOTALL)
    if not match:
        return None
    inner = match.group(1)
    inner = inner.replace("<br><br>", "\n\n").replace("<br /><br />", "\n\n")
    inner = inner.replace("<br>", "\n").replace("<br />", "\n")
    return html_module.unescape(inner)


def canonical_index(snapshot):
    """email -> (record_id, contact_key, cadence-for-that-contact).

    Lower-cased, because the provider echoes whatever case the lead was
    created with and an address is not case sensitive in the half that
    matters here.
    """
    index = {}
    for record in snapshot:
        cadence = record.get("cadence") or {}
        for contact in (record.get("contacts") or []):
            email = (contact.get("email") or "").strip().lower()
            if not email:
                continue
            key = contact.get("key")
            index[email] = (record.get("id"), key, cadence.get(key) or {})
    return index


def step_keys(provider_campaign_id, canonical_row, bison):
    """sequence_step_id -> cadence key, by ORDINAL.

    The provider numbers its own steps and the canonical row lists ours in
    order; the join is position, which is the only thing both sides agree on.
    A campaign whose step counts differ returns {} and the caller reports it
    rather than guessing a pairing.
    """
    steps = bison.sequence_steps(provider_campaign_id) or []
    ours = [s.get("key") for s in (canonical_row.get("cadence_steps") or [])]
    if len(steps) != len(ours):
        return {}
    out = {}
    for position, step in enumerate(steps):
        ident = step.get("id")
        if ident is not None:
            out[ident] = ours[position]
    return out


def check(provider_campaign_id, snapshot, campaign_rows, bison):
    canonical_row = None
    for row in campaign_rows:
        if str(row.get("bison_campaign_id")) == str(provider_campaign_id):
            canonical_row = row
            break
    if canonical_row is None:
        return [("campaign", str(provider_campaign_id), "FAIL",
                 "no canonical campaign names this provider id")]

    index = canonical_index(snapshot)
    keys = step_keys(provider_campaign_id, canonical_row, bison)
    rows = bison.scheduled_emails(provider_campaign_id) or []
    findings = []
    if not rows:
        findings.append(("queue", str(provider_campaign_id), "EMPTY",
                         "no rendered rows to compare - nothing is queued"))
        return findings
    if not keys:
        findings.append(("steps", str(provider_campaign_id), "FAIL",
                         "provider step count does not match cadence_steps; "
                         "no pairing is safe"))
        return findings

    for row in rows:
        lead = row.get("lead") or {}
        email = (lead.get("email") or "").strip().lower()
        where = "%s/%s" % (provider_campaign_id, email or row.get("id"))
        entry = index.get(email)
        if entry is None:
            findings.append(("lead", where, "FAIL",
                             "queued for an address no canonical record "
                             "holds"))
            continue
        record_id, contact_key, cadence = entry
        key = keys.get(row.get("sequence_step_id"))
        if key is None:
            findings.append(("step", where, "FAIL",
                             "row names sequence_step_id "
                             f"{row.get('sequence_step_id')}, which is not a "
                             "step of this campaign"))
            continue
        approved = cadence.get(key) or {}
        if not approved.get("body"):
            findings.append(("copy", where, "FAIL",
                             f"{record_id}:{contact_key}:{key} has no "
                             "canonical body"))
            continue

        want_subject = approved.get("subject") or ""
        got_subject = row.get("email_subject") or ""
        # The provider owns the `Re: ` on a threaded step, and the sequence
        # readback already proves which steps carry it. Compared bare here so
        # a follow-up is not reported as a subject change every run.
        bare = re.sub(r"^(?:Re:\s*)+", "", got_subject)
        # NOT unescaped, deliberately, unlike the body. A subject line is a
        # mail header rather than HTML, so an entity that reached it would be
        # read literally by the prospect. If the provider ever escapes one,
        # this must fail rather than absorb it.
        row_ok = True
        if bare != want_subject:
            row_ok = False
            findings.append(("subject", "%s:%s" % (where, key), "FAIL",
                             "queued %r != approved %r" % (bare, want_subject)))

        got_body = unwrap(row.get("email_body"))
        if got_body is None:
            row_ok = False
            findings.append(("body", "%s:%s" % (where, key), "FAIL",
                             "queued body is not the shape the factory "
                             "writes: %r" % (str(row.get('email_body'))[:80],)))
        elif got_body != approved.get("body"):
            row_ok = False
            findings.append(("body", "%s:%s" % (where, key), "FAIL",
                             _first_difference(approved.get("body"),
                                               got_body)))

        # A row PASSes only when BOTH halves did. The first version emitted
        # the PASS from the body comparison's `else`, so a row with a wrong
        # SUBJECT and a right body produced a FAIL and a PASS - which inflates
        # the "N rows carry the approved text" count and gives an operator
        # scanning for PASS lines a reason to believe the row was fine.
        if row_ok:
            findings.append(("row", "%s:%s" % (where, key), "PASS",
                             "subject and body are the approved text"))
    return findings


def _first_difference(want, got):
    """Where they part, and what is on each side there.

    A diff of two four-hundred-character bodies is unreadable in a terminal
    and the thing worth seeing is the first character that differs, which is
    almost always an unresolved variable or a substituted name.
    """
    for position, (a, b) in enumerate(zip(want, got)):
        if a != b:
            return ("differs at %d: approved ...%r... queued ...%r..."
                    % (position, want[max(0, position - 20):position + 30],
                       got[max(0, position - 20):position + 30]))
    if len(want) != len(got):
        return ("same to %d chars then one is longer: approved %d, queued %d"
                % (min(len(want), len(got)), len(want), len(got)))
    return "differ but no differing character was found"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("campaigns", nargs="+", type=int,
                        help="EmailBison campaign ids")
    args = parser.parse_args(argv)

    _setup_data_access()
    from src import store
    from src.providers import bison

    snapshot = store.load()
    campaign_rows = [r for r in store.read_jsonl(store.campaigns_path())]

    failures = 0
    for provider_campaign_id in args.campaigns:
        print("=" * 78)
        print("  QUEUED COPY READBACK - EmailBison campaign "
              f"{provider_campaign_id}")
        print("=" * 78)
        findings = check(provider_campaign_id, snapshot, campaign_rows, bison)
        for kind, where, verdict, detail in findings:
            if verdict == "PASS":
                print(f"  PASS  {kind:8} {where}")
            else:
                failures += 1
                print(f"  {verdict:5} {kind:8} {where}")
                print(f"           {detail}")
        passed = sum(1 for f in findings if f[2] == "PASS")
        print(f"  ---- {passed} rows carry the approved text, "
              f"{len(findings) - passed} do not")
    print("=" * 78)
    print("  VERDICT:", "PASS" if not failures else f"FAIL ({failures})")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
