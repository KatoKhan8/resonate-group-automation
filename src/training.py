"""Training pair capture at the moment of approval.

OPERATOR DECISION, 2026-09-25: every APPROVED review file feeds work/training/.
At 5,000 pairs, fine-tune Qwen 32B and rerun the blind A/B.

WHY THE CAPTURE IS URGENT AND THE FINE-TUNE IS NOT.

The fine-tune is far off - 5,000 pairs at ~50 a night is months. The capture
is urgent for one reason: a pair not written when the file is approved is gone
for good. Approval is the only moment the ground truth exists, because approval
is what makes the copy correct rather than merely generated.

WHERE IT HOOKS.

`reviewapproval.record()` is the only function that knows an approval happened.
The capture runs there, not in the pipeline - the pipeline runs whether or not
the operator ever approves, and that is exactly the distinction that matters.

WHAT A PAIR IS.

    input   what the writer saw: the extracted facts, the angle, the persona,
            the company hook, the lead's role - the record data
    output  what the operator APPROVED: subject, body for each step

Record alongside each pair: the review file hash, the campaign, the model that
wrote it, the confidence it claimed, and the approval row.

HELD LEADS.

Held leads are captured too, separately, as negative examples: the facts that
did NOT support a first line are as instructive as the ones that did.

RULES.

- work/ is gitignored and this is real prospect copy. It stays local.
- One JSONL row per pair, append-only, never rewritten.
- A counter the operator can read: how many pairs, how many held, how far from
  5,000.
"""
import json
import os
import re

from . import store


TARGET = 5000


def path():
    """Where training pairs live. Beside the queue, not in git."""
    return os.path.abspath(os.environ.get("TRAINING")
                           or os.path.join(os.path.dirname(store.queue_path()),
                                           "training", "pairs.jsonl"))


def _parse_review_html(html_text):
    """Extract lead data from the review HTML.

    Each card has: company, contact (name, title, email), lane, day, status,
    subject, body. Returns a list of dicts.
    """
    cards = []
    # Each article is one card
    article_pattern = re.compile(
        r'<article class="(\w+)">(.*?)</article>',
        re.DOTALL
    )
    for match in article_pattern.finditer(html_text):
        status = match.group(1)
        content = match.group(2)

        card = {"status": status}

        # Company
        company_match = re.search(r'<h2>([^<]+)</h2>', content)
        if company_match:
            card["company"] = company_match.group(1).strip()

        # Contact metadata
        meta_match = re.search(
            r'<div class=meta>([^<]+) &middot; ([^<]+) &middot; '
            r'<code>([^<]+)</code> &middot; ([^<]+)</div>',
            content
        )
        if meta_match:
            card["contact_name"] = meta_match.group(1).strip()
            card["contact_title"] = meta_match.group(2).strip()
            card["contact_email"] = meta_match.group(3).strip()
            card["contact_verdict"] = meta_match.group(4).strip()

        # Why (hook or diagnosis)
        why_match = re.search(r'<p class=why>(.*?)</p>', content, re.DOTALL)
        if why_match:
            card["why"] = re.sub(r'<[^>]+>', '', why_match.group(1)).strip()

        # Subject
        subject_match = re.search(r'<div class=subject>([^<]+)</div>', content)
        if subject_match:
            card["subject"] = subject_match.group(1).strip()

        # Body
        body_match = re.search(r'<pre>(.*?)</pre>', content, re.DOTALL)
        if body_match:
            card["body"] = body_match.group(1).strip()

        # Lane and day from tags
        lane_match = re.search(r'<span class=lane>([^<]+)</span>', content)
        if lane_match:
            card["lane"] = lane_match.group(1).strip()

        day_match = re.search(r'<span class=day>([^<]+)</span>', content)
        if day_match:
            card["day"] = day_match.group(1).strip()

        cards.append(card)

    return cards


def _find_record_by_email(email, recs):
    """Find the record containing this contact email."""
    email = (email or "").strip().lower()
    if not email:
        return None, None
    for rec in recs:
        for contact in rec.get("contacts") or []:
            if (contact.get("email") or "").strip().lower() == email:
                return rec, contact
    return None, None


def _extract_input(rec, contact):
    """The input half of the training pair: what the writer saw."""
    facts = []
    for entry in rec.get("research") or []:
        if entry.get("field") and entry.get("text"):
            facts.append({"field": entry["field"], "text": entry["text"]})

    return {
        "lead_name": contact.get("name"),
        "lead_title": contact.get("title"),
        "company": rec.get("company"),
        "domain": rec.get("domain"),
        "lane": rec.get("lane"),
        "angle": contact.get("angle"),
        "persona": contact.get("persona"),
        "facts": facts[:5],
        "company_hook": rec.get("hook"),
    }


def _extract_output(card, rec, contact):
    """The output half: what the operator approved.

    The review file shows the assembled copy (subject, body). The spans
    (first_line, bridges, linkedin) are not in the review file, so we extract
    what we can: subject and first line from the body.
    """
    body = card.get("body") or ""
    first_line = body.split("\n")[0].strip() if body else ""

    return {
        "subject": card.get("subject"),
        "first_line": first_line,
        "body": body,
    }


def capture_on_approval(campaign, review_hash, approval_row, recs=None):
    """Called by reviewapproval.record() after writing the approval.

    Finds the review file, checks its hash, and captures pairs if the hash
    matches. Best-effort: if the file is gone or the hash doesn't match,
    returns 0 without raising.

    `recs` is the current records. If None, loads from the queue.
    """
    review_file = os.path.join(store.out_dir(), "review.html")
    if not os.path.exists(review_file):
        return 0

    try:
        from . import reviewapproval
        actual_hash = reviewapproval.file_hash(review_file)
    except (IOError, OSError):
        return 0

    if actual_hash != str(review_hash):
        return 0

    return capture_from_review_file(
        review_file, campaign, review_hash,
        approval_row.get("by", ""), approval_row, recs)


def capture_from_review_file(review_file_path, campaign, review_hash, by,
                             approval_row, recs=None):
    """Extract training pairs from an approved review file.

    Reads the review HTML, matches each card against the records, and writes
    one training pair per lead. Returns the number of pairs written.

    `recs` is the current records. If None, loads from the queue.
    """
    if recs is None:
        recs = store.load()

    try:
        with open(review_file_path, encoding="utf-8") as f:
            html_text = f.read()
    except (FileNotFoundError, IOError):
        return 0

    cards = _parse_review_html(html_text)
    if not cards:
        return 0

    pairs_path = path()
    store.refuse_production_write(pairs_path)
    os.makedirs(os.path.dirname(pairs_path), exist_ok=True)

    written = 0
    with store.lock(for_path=pairs_path):
        with open(pairs_path, "a", encoding="utf-8") as out:
            for card in cards:
                email = card.get("contact_email")
                rec, contact = _find_record_by_email(email, recs)
                if rec is None:
                    continue

                status = card.get("status")
                held = status == "held"

                pair = {
                    "at": store.now(),
                    "campaign": str(campaign),
                    "review_hash": str(review_hash),
                    "approval_by": str(by),
                    "record_id": rec.get("id"),
                    "contact_email": email,
                    "held": held,
                    "hold_reason": card.get("why") if held else None,
                    "input": _extract_input(rec, contact),
                    "output": _extract_output(card, rec, contact),
                }

                out.write(json.dumps(pair, ensure_ascii=False) + "\n")
                written += 1

    return written


def count():
    """How many pairs, how many held, how far from 5,000.

    The counter the operator can read.
    """
    pairs_path = path()
    if not os.path.exists(pairs_path):
        return {"pairs": 0, "held": 0, "approved": 0, "remaining": TARGET}

    total = 0
    held = 0
    with open(pairs_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                total += 1
                if row.get("held"):
                    held += 1
            except json.JSONDecodeError:
                continue

    approved = total - held
    return {
        "pairs": total,
        "held": held,
        "approved": approved,
        "remaining": max(0, TARGET - approved),
    }
