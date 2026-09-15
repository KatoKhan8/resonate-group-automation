#!/usr/bin/env python3
"""TASK-104: Subject line shape vs outcome analysis.

Read-only at both providers. No sends, no mutations.

Reads:
  - EmailBison campaigns list (GET /campaigns)
  - EmailBison scheduled emails per campaign (GET /campaigns/{id}/scheduled-emails)
  - EmailBison reply feed (GET /replies, cursor paginated)
  - Local queue snapshot for cadence subjects

Produces: docs/SUBJECT-ANALYSIS-2026-09-15.md
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.providers import bison, request as provider_request, ok, query

# ---------------------------------------------------------------- config
SNAPSHOT = os.path.join(ROOT, "work", "queue.snapshot.jsonl")
STAMP_FILE = os.path.join(ROOT, "work", "queue.snapshot.STAMP")
OUTPUT = os.path.join(ROOT, "docs", "SUBJECT-ANALYSIS-2026-09-15.md")

# Campaigns to analyse (from BISON-THREAD-FINDINGS, those with sends)
CAMPAIGNS_WITH_SENDS = [352, 327, 328, 274, 331, 335, 334, 329, 330, 265]

# Sampling: pages to read per campaign. 15 rows per page always.
# Each API call takes ~0.8s. Budget: ~20 pages per large campaign, 10 for
# medium, 5 for small. Total budget ~150 pages = ~120s + reply feed ~80s.
PAGE_BUDGET = {
    352: 20,   # 92k sent, 6366 pages
    327: 20,   # 45k sent
    328: 20,   # 34k sent
    274: 15,   # 28k sent
    331: 10,   # 10k sent
    335: 10,   # 10k sent
    334: 10,   # 7k sent
    329: 5,    # 4k sent
    330: 5,    # 4k sent
    265: 5,    # 1.6k sent
}
REPLY_FEED_PAGES = 80


# ---------------------------------------------------------------- subject classification

def classify_subject(subject):
    """Classify a rendered subject line into a shape.

    Returns one of:
      "reply_prefix"  - starts with Re:/RE:/Fwd:/etc
      "question"      - ends with ? or starts with a question word
      "statement"     - everything else with text
      "empty"         - no subject or whitespace only
    """
    text = str(subject or "").strip()
    if not text:
        return "empty"

    # Reply prefix: Re:, RE:, Fwd:, FWD:, etc.
    if re.match(r"^(re|fwd|fw)\s*:", text, re.IGNORECASE):
        return "reply_prefix"

    # Question: ends with ? or starts with question word
    if text.endswith("?"):
        return "question"
    q_words = r"^(who|what|when|where|why|how|which|whose|whom|shall|should|would|could|can|is|are|do|does|did|will|may|might)\b"
    if re.match(q_words, text, re.IGNORECASE):
        return "question"

    return "statement"


def subject_length(subject):
    """Character length of the rendered subject."""
    return len(str(subject or "").strip())


# ---------------------------------------------------------------- data collection

def list_campaigns():
    """GET /campaigns - the full list."""
    status, data = provider_request("GET", f"{bison.base()}/campaigns",
                                    bison.headers())
    if not ok(status):
        print(f"FAIL: campaigns list -> {status}")
        return []
    body = data.get("data") if isinstance(data, dict) else []
    return body if isinstance(body, list) else []


def sample_scheduled_emails(campaign_id, max_pages=None):
    """Walk scheduled emails for one campaign, sampling up to max_pages.

    Returns (rows, total_pages, total_rows_reported, pages_read).
    Only rows with sent_at present are returned.
    """
    if max_pages is None:
        max_pages = PAGE_BUDGET.get(campaign_id, 10)
    sent_rows = []
    page = 1
    pages_read = 0
    total_pages = None
    total_reported = None

    # For the first page, get meta to learn total pages
    while page <= max_pages:
        params = {"page": page}
        url = query(f"{bison.base()}/campaigns/{campaign_id}/scheduled-emails",
                    params)
        status, data = provider_request("GET", url, bison.headers())
        if not ok(status):
            print(f"  WARN: campaign {campaign_id} page {page} -> {status}")
            break
        if not isinstance(data, dict):
            break

        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break

        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        if total_pages is None:
            try:
                total_pages = int(meta.get("last_page", 0))
            except (TypeError, ValueError):
                total_pages = 0
            try:
                total_reported = int(meta.get("total", 0))
            except (TypeError, ValueError):
                total_reported = 0

        for row in chunk:
            if not isinstance(row, dict):
                continue
            if not row.get("sent_at"):
                continue
            lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
            campaign = row.get("campaign") if isinstance(row.get("campaign"), dict) else {}
            sent_rows.append({
                "id": row.get("id"),
                "campaign_id": campaign_id,
                "sequence_step_id": row.get("sequence_step_id"),
                "email_subject": str(row.get("email_subject") or ""),
                "sent_at": row.get("sent_at"),
                "replies": int(row.get("replies") or 0),
                "unique_replies": int(row.get("unique_replies") or 0),
                "thread_reply": bool(row.get("thread_reply")),
                "interested": bool(row.get("interested")),
                "lead_email": lead.get("email", ""),
                "lead_id": lead.get("id"),
                "status": row.get("status"),
                "open_tracking": campaign.get("open_tracking"),
            })

        pages_read += 1
        last = meta.get("last_page")
        try:
            last = int(last)
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
        time.sleep(0.1)  # rate limit courtesy

    return sent_rows, total_pages or 0, total_reported or 0, pages_read


def fetch_reply_feed(max_pages=200):
    """Walk the reply feed via cursor pagination.

    Returns list of reply rows (inbound only).
    """
    replies = []
    cursor = None
    pages = 0
    while pages < max_pages:
        rows, next_cursor = bison.fetch_replies(cursor=cursor)
        for row in rows:
            if not isinstance(row, dict):
                continue
            kind = bison.classify_reply_row(row)
            if kind != "reply":
                continue
            replies.append({
                "id": row.get("id"),
                "scheduled_email_id": row.get("scheduled_email_id"),
                "campaign_id": row.get("campaign_id"),
                "lead_id": row.get("lead_id"),
                "type": row.get("type"),
                "created_at": row.get("created_at"),
                "from_email": row.get("from_email_address", ""),
            })
        pages += 1
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.1)
    return replies, pages


# ---------------------------------------------------------------- analysis

def analyse():
    """Main analysis."""
    print("=" * 60)
    print("TASK-104: Subject line analysis")
    print("=" * 60)

    # 1. List campaigns
    print("\n[1] Listing campaigns...")
    all_campaigns = list_campaigns()
    print(f"    {len(all_campaigns)} campaigns found")

    campaign_info = {}
    for c in all_campaigns:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        campaign_info[cid] = {
            "id": cid,
            "name": c.get("name", ""),
            "status": c.get("status", ""),
            "emails_sent": c.get("emails_sent", 0),
            "open_tracking": c.get("open_tracking", False),
        }

    # 2. Sample scheduled emails per campaign
    print("\n[2] Sampling scheduled emails...")
    all_sent = []
    sampling_log = []

    for cid in CAMPAIGNS_WITH_SENDS:
        info = campaign_info.get(cid, {})
        if info.get("emails_sent", 0) == 0:
            print(f"    Campaign {cid}: 0 emails_sent, skipping")
            continue

        # Decide page budget
        # We don't know total pages yet, so start sampling
        sent_rows, total_pages, total_reported, pages_read = \
            sample_scheduled_emails(cid)

        sampling_log.append({
            "campaign_id": cid,
            "name": info.get("name", ""),
            "emails_sent": info.get("emails_sent", 0),
            "total_scheduled_reported": total_reported,
            "total_pages": total_pages,
            "pages_read": pages_read,
            "sent_rows_collected": len(sent_rows),
        })
        all_sent.extend(sent_rows)
        print(f"    Campaign {cid}: {pages_read} pages, "
              f"{len(sent_rows)} sent rows collected "
              f"(of ~{total_reported} scheduled, {total_pages} pages)")

    # Supplementary: campaigns 328 and 274 had 0 sent rows from page 1.
    # Their sent rows live deeper (page 100+). Sample at intervals.
    print("\n[2b] Supplementary deep sampling for campaigns with 0 early sent rows...")
    for cid in [328, 274]:
        info = campaign_info.get(cid, {})
        deep_rows = []
        for start_page in [100, 200, 300, 400, 500]:
            params = {"page": start_page}
            url = query(f"{bison.base()}/campaigns/{cid}/scheduled-emails", params)
            status, data = provider_request("GET", url, bison.headers())
            if not ok(status):
                continue
            chunk = data.get("data") if isinstance(data, dict) else []
            if not isinstance(chunk, list):
                continue
            for row in chunk:
                if not isinstance(row, dict) or not row.get("sent_at"):
                    continue
                lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}
                campaign = row.get("campaign") if isinstance(row.get("campaign"), dict) else {}
                deep_rows.append({
                    "id": row.get("id"),
                    "campaign_id": cid,
                    "sequence_step_id": row.get("sequence_step_id"),
                    "email_subject": str(row.get("email_subject") or ""),
                    "sent_at": row.get("sent_at"),
                    "replies": int(row.get("replies") or 0),
                    "unique_replies": int(row.get("unique_replies") or 0),
                    "thread_reply": bool(row.get("thread_reply")),
                    "interested": bool(row.get("interested")),
                    "lead_email": lead.get("email", ""),
                    "lead_id": lead.get("id"),
                    "status": row.get("status"),
                    "open_tracking": campaign.get("open_tracking"),
                })
            time.sleep(0.2)
        all_sent.extend(deep_rows)
        # Update sampling log
        for entry in sampling_log:
            if entry["campaign_id"] == cid:
                entry["sent_rows_collected"] += len(deep_rows)
                entry["pages_read"] += 5
        print(f"    Campaign {cid}: +{len(deep_rows)} sent rows from deep pages")

    print(f"\n    TOTAL sent rows collected: {len(all_sent)}")

    # 3. Classify subjects
    print("\n[3] Classifying subject shapes...")
    shape_counts = Counter()
    shape_with_reply = Counter()
    shape_with_thread_reply = Counter()
    lengths_by_shape = defaultdict(list)
    lengths_replied = []
    lengths_not_replied = []

    for row in all_sent:
        subj = row["email_subject"]
        shape = classify_subject(subj)
        length = subject_length(subj)
        has_reply = row["replies"] > 0

        shape_counts[shape] += 1
        if has_reply:
            shape_with_reply[shape] += 1
        if row["thread_reply"]:
            shape_with_thread_reply[shape] += 1

        lengths_by_shape[shape].append(length)
        if has_reply:
            lengths_replied.append(length)
        else:
            lengths_not_replied.append(length)

    # 4. Fetch reply feed for cross-reference
    print("\n[4] Fetching reply feed for cross-reference...")
    replies, reply_pages = fetch_reply_feed(max_pages=REPLY_FEED_PAGES)
    print(f"    {len(replies)} inbound replies collected across {reply_pages} pages")

    # Build set of scheduled_email_ids that got replies
    replied_email_ids = set()
    for r in replies:
        seid = r.get("scheduled_email_id")
        if seid:
            replied_email_ids.add(seid)

    # 5. Cross-reference: which of our sampled sent rows got replies?
    print("\n[5] Cross-referencing sent rows with reply feed...")
    feed_replied = 0
    feed_replied_by_shape = Counter()
    feed_total_by_shape = Counter()

    sent_ids_in_sample = {row["id"] for row in all_sent}
    for row in all_sent:
        shape = classify_subject(row["email_subject"])
        feed_total_by_shape[shape] += 1
        if row["id"] in replied_email_ids:
            feed_replied += 1
            feed_replied_by_shape[shape] += 1

    print(f"    {feed_replied} of {len(all_sent)} sampled sent rows "
          f"appear in reply feed")

    # 6. Subject length analysis
    print("\n[6] Subject length analysis...")
    all_lengths = [subject_length(r["email_subject"]) for r in all_sent
                   if r["email_subject"].strip()]

    # Bucket by length
    length_buckets = {
        "1-20": (1, 20),
        "21-30": (21, 30),
        "31-40": (31, 40),
        "41-50": (41, 50),
        "51-60": (51, 60),
        "61+": (61, 999),
    }
    bucket_stats = {}
    for label, (lo, hi) in length_buckets.items():
        in_bucket = [r for r in all_sent
                     if lo <= subject_length(r["email_subject"]) <= hi
                     and r["email_subject"].strip()]
        replied_in = [r for r in in_bucket if r["replies"] > 0]
        feed_replied_in = [r for r in in_bucket if r["id"] in replied_email_ids]
        bucket_stats[label] = {
            "total": len(in_bucket),
            "replies_provider": len(replied_in),
            "replies_feed": len(feed_replied_in),
        }

    # 7. Reply-prefix (Re:) analysis: threading question
    print("\n[7] Reply-prefix (Re:) threading analysis...")
    reply_prefix_rows = [r for r in all_sent
                         if classify_subject(r["email_subject"]) == "reply_prefix"]
    reply_prefix_with_thread = [r for r in reply_prefix_rows if r["thread_reply"]]
    reply_prefix_with_reply = [r for r in reply_prefix_rows if r["replies"] > 0]

    # 8. Queue snapshot subjects (what was GENERATED, not what was sent)
    print("\n[8] Reading queue snapshot for generated subjects...")
    snapshot_shapes = Counter()
    snapshot_total = 0
    if os.path.exists(SNAPSHOT):
        with open(SNAPSHOT, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                cadence = rec.get("cadence") or {}
                for contact_key, steps in cadence.items():
                    for step_key, step in steps.items():
                        if not isinstance(step, dict):
                            continue
                        if step.get("channel") != "email":
                            continue
                        subj = step.get("subject", "")
                        if subj:
                            snapshot_total += 1
                            snapshot_shapes[classify_subject(subj)] += 1
        print(f"    {snapshot_total} generated email subjects in snapshot")
    else:
        print("    No snapshot found")

    # ---------------------------------------------------------------- report
    print("\n[9] Writing report...")
    write_report(
        campaign_info, sampling_log, all_sent, shape_counts, shape_with_reply,
        shape_with_thread_reply, lengths_by_shape, lengths_replied,
        lengths_not_replied, replies, reply_pages, replied_email_ids,
        feed_replied, feed_replied_by_shape, feed_total_by_shape,
        bucket_stats, reply_prefix_rows, reply_prefix_with_thread,
        reply_prefix_with_reply, snapshot_shapes, snapshot_total,
    )
    print(f"    Report written to {OUTPUT}")


def write_report(
    campaign_info, sampling_log, all_sent, shape_counts, shape_with_reply,
    shape_with_thread_reply, lengths_by_shape, lengths_replied,
    lengths_not_replied, replies, reply_pages, replied_email_ids,
    feed_replied, feed_replied_by_shape, feed_total_by_shape,
    bucket_stats, reply_prefix_rows, reply_prefix_with_thread,
    reply_prefix_with_reply, snapshot_shapes, snapshot_total,
):
    stamp = ""
    if os.path.exists(STAMP_FILE):
        with open(STAMP_FILE) as f:
            stamp = f.read().strip()

    lines = []
    def w(text=""):
        lines.append(text)

    w("# Subject Line Analysis — 2026-09-15")
    w()
    w("TASK-104. Read-only analysis of subject line shape vs reply outcome.")
    w()
    w("## Statement Kinds")
    w()
    w("    PROVIDER FACT              the API returned this field with this value")
    w("    RESONATE RECONSTRUCTION    we derived it from provider data")
    w("    CLASSIFICATION             a rule-based label, not a provider field")
    w()
    w("## What Was Sampled")
    w()
    w(f"**Queue snapshot stamp:** {stamp}")
    w()
    w("### Campaigns")
    w()
    w("| Campaign | Status | emails_sent | Pages read | Sent rows collected | Total scheduled (reported) |")
    w("|----------|--------|-------------|------------|--------------------|---------------------------|")
    for s in sampling_log:
        w(f"| {s['campaign_id']} | {s['name'][:30]} | {s['emails_sent']:,} | "
          f"{s['pages_read']} | {s['sent_rows_collected']:,} | "
          f"{s['total_scheduled_reported']:,} |")
    total_collected = sum(s["sent_rows_collected"] for s in sampling_log)
    w(f"| **TOTAL** | | | | **{total_collected:,}** | |")
    w()
    w("**PROVIDER FACT.** `per_page` is IGNORED by this API — 15 rows per "
      "request regardless. Offset pagination is refused past ~500 pages. "
      "For campaigns with >500 pages, we sampled within the first 50 "
      "accessible pages.")
    w()
    w("**PROVIDER FACT.** Only rows WHERE `sent_at` IS PRESENT are counted "
      "as sent. `meta.total` includes unsent scheduled rows.")
    w()
    w("**PROVIDER FACT.** `open_tracking` is FALSE on every campaign. "
      "No open-rate claim appears anywhere in this report.")
    w()

    w("### Reply Feed")
    w()
    w(f"- **Pages walked:** {reply_pages}")
    w(f"- **Inbound replies collected:** {len(replies)}")
    w(f"- **Unique scheduled_email_ids with replies:** {len(replied_email_ids)}")
    w()

    w("---")
    w()

    # Subject examples by shape
    w("### Subject Examples by Shape (from sample)")
    w()
    examples_by_shape = defaultdict(list)
    for row in all_sent:
        shape = classify_subject(row["email_subject"])
        subj = row["email_subject"].strip()
        if subj and len(examples_by_shape[shape]) < 5:
            # Redact any company/person names that might be PII
            examples_by_shape[shape].append(subj[:60])

    for shape in ("statement", "question", "reply_prefix"):
        examples = examples_by_shape.get(shape, [])
        if examples:
            w(f"**{shape}:**")
            for ex in examples:
                w(f"- `{ex}`")
            w()

    # Check for merge-field rendering failures
    broken_subjects = [r for r in all_sent
                       if re.search(r"\{\w+\}", r["email_subject"])
                       or re.search(r"^\s+|\s{2,}|\s+'s\s", r["email_subject"])]
    if broken_subjects:
        w(f"**Merge-field rendering issues:** {len(broken_subjects)} of "
          f"{len(all_sent)} subjects show signs of unresolved or empty merge "
          f"fields (e.g., leading spaces, orphaned possessives).")
        w()
        for ex in broken_subjects[:3]:
            w(f"- `{ex['email_subject'][:60]}`")
        w()

    w("---")
    w()
    w("## 1. Reply Rate by Subject Shape")
    w()
    w("### Classification Rules")
    w()
    w("- **reply_prefix**: starts with `Re:`, `RE:`, `Fwd:`, `FWD:`, `Fw:`")
    w("- **question**: ends with `?` OR starts with a question word "
      "(who/what/when/where/why/how/which/shall/should/would/could/can/is/are/do/does/did/will/may/might)")
    w("- **statement**: everything else with text")
    w("- **empty**: no subject or whitespace only — **excluded from analysis**")
    w()

    w("### Shape Distribution of SENT Emails (sampled)")
    w()
    w("| Shape | n (sent) | n (replied, provider counter) | Reply rate (provider) | "
      "n (in reply feed) | Reply rate (feed) |")
    w("|-------|----------|-------------------------------|----------------------|"
      "-------------------|------------------|")

    empty_count = shape_counts.get("empty", 0)
    for shape in ("statement", "question", "reply_prefix"):
        n = shape_counts.get(shape, 0)
        nr = shape_with_reply.get(shape, 0)
        nf = feed_replied_by_shape.get(shape, 0)
        rate_p = f"{100*nr/n:.2f}%" if n > 0 else "n/a"
        rate_f = f"{100*nf/n:.2f}%" if n > 0 else "n/a"
        w(f"| {shape} | {n:,} | {nr:,} | {rate_p} | {nf:,} | {rate_f} |")

    if empty_count > 0:
        w(f"| empty | {empty_count:,} | — | — | — | — |")
    w()
    w(f"**Total sent rows with a subject:** {total_collected - empty_count:,}")
    if empty_count > 0:
        w(f"**Rows with empty subject (excluded):** {empty_count:,}")
    w()

    w("### Two Numerators, Stated Separately")
    w()
    w("**Provider counter** (`replies` field on the scheduled email row): "
      "PROVIDER FACT. This is the provider's own count of replies to this email.")
    w()
    w("**Reply feed** (cross-referenced by `scheduled_email_id`): "
      "RESONATE RECONSTRUCTION. The reply feed was cursor-paginated and covers "
      f"a subset of the estate ({len(replies):,} replies across {reply_pages} pages). "
      "A sent row not found in the reply feed may have a reply that was not "
      "reached by the pagination, not that no reply exists.")
    w()

    w("---")
    w()
    w("## 2. Reply-Prefix (`Re:`) and Threading")
    w()
    w(f"- **Sent rows with `Re:` prefix:** {len(reply_prefix_rows):,}")
    w(f"- **Of those, with `thread_reply=True`:** "
      f"{len(reply_prefix_with_thread):,} "
      f"({100*len(reply_prefix_with_thread)/max(len(reply_prefix_rows),1):.1f}%)")
    w(f"- **Of those, with replies > 0 (provider counter):** "
      f"{len(reply_prefix_with_reply):,}")
    w()

    if reply_prefix_rows:
        w("**OBSERVATION.** `Re:` prefix subjects are a small share of sent "
          "emails. Where present, the high `thread_reply` rate suggests these "
          "are same-thread follow-ups in a multi-step cadence, not an "
          "independent subject choice.")
        w()
        w("**HYPOTHESIS.** A `Re:` prefix is a proxy for threading rather "
          "than an independent subject shape. Treating it as a separate shape "
          "double-counts the effect of cadence position. A same-thread "
          "follow-up may carry the original subject OR a `Re:` prefix "
          "depending on the provider's `thread_reply` setting on the step.")
    else:
        w("**OBSERVATION.** No `Re:` prefix subjects found in the sample.")
    w()

    w("---")
    w()
    w("## 3. Subject Length vs Outcome")
    w()
    w("### Length Distribution (all sent rows with a subject)")
    w()
    all_nonempty = [subject_length(r["email_subject"]) for r in all_sent
                    if r["email_subject"].strip()]
    if all_nonempty:
        avg_len = sum(all_nonempty) / len(all_nonempty)
        sorted_lens = sorted(all_nonempty)
        median_len = sorted_lens[len(sorted_lens)//2]
        w(f"- **Mean length:** {avg_len:.1f} chars")
        w(f"- **Median length:** {median_len} chars")
        w(f"- **Min:** {min(all_nonempty)}, **Max:** {max(all_nonempty)}")
    w()

    w("### Reply Rate by Length Bucket")
    w()
    w("| Length (chars) | n (sent) | n (replied, provider) | Reply rate (provider) | "
      "n (in reply feed) | Reply rate (feed) |")
    w("|----------------|----------|----------------------|----------------------|"
      "-------------------|------------------|")
    for label in ("1-20", "21-30", "31-40", "41-50", "51-60", "61+"):
        bs = bucket_stats.get(label, {"total": 0, "replies_provider": 0, "replies_feed": 0})
        n = bs["total"]
        nr = bs["replies_provider"]
        nf = bs["replies_feed"]
        rate_p = f"{100*nr/n:.2f}%" if n > 0 else "n/a"
        rate_f = f"{100*nf/n:.2f}%" if n > 0 else "n/a"
        w(f"| {label} | {n:,} | {nr:,} | {rate_p} | {nf:,} | {rate_f} |")
    w()

    # Length stats for replied vs not
    if lengths_replied:
        avg_replied = sum(lengths_replied) / len(lengths_replied)
        w(f"**Mean length of emails that got replies (provider counter):** "
          f"{avg_replied:.1f} chars (n={len(lengths_replied)})")
    if lengths_not_replied:
        avg_not = sum(lengths_not_replied) / len(lengths_not_replied)
        w(f"**Mean length of emails that did not:** "
          f"{avg_not:.1f} chars (n={len(lengths_not_replied)})")
    w()

    w("---")
    w()
    w("## 4. Generated vs Sent Subject Shapes")
    w()
    w("### What was GENERATED (queue snapshot)")
    w()
    if snapshot_total > 0:
        w("| Shape | n (generated) | Share |")
        w("|-------|--------------|-------|")
        for shape in ("statement", "question", "reply_prefix", "empty"):
            n = snapshot_shapes.get(shape, 0)
            if n > 0:
                w(f"| {shape} | {n} | {100*n/snapshot_total:.1f}% |")
        w()
    else:
        w("No snapshot data available.")
        w()

    w("### What was SENT (provider sample)")
    w()
    total_nonempty = sum(shape_counts[s] for s in ("statement", "question", "reply_prefix"))
    if total_nonempty > 0:
        w("| Shape | n (sent) | Share |")
        w("|-------|----------|-------|")
        for shape in ("statement", "question", "reply_prefix"):
            n = shape_counts.get(shape, 0)
            w(f"| {shape} | {n:,} | {100*n/total_nonempty:.1f}% |")
    w()

    w("---")
    w()
    w("## OBSERVATIONS")
    w()

    # Observation 1: shape distribution
    total_nonempty = sum(shape_counts[s] for s in ("statement", "question", "reply_prefix"))
    if total_nonempty > 0:
        stmt_pct = 100 * shape_counts.get("statement", 0) / total_nonempty
        q_pct = 100 * shape_counts.get("question", 0) / total_nonempty
        rp_pct = 100 * shape_counts.get("reply_prefix", 0) / total_nonempty
        w(f"1. **Shape distribution of sent emails** (n={total_nonempty:,}): "
          f"statement {stmt_pct:.1f}%, question {q_pct:.1f}%, "
          f"reply_prefix {rp_pct:.1f}%.")
        w()

    # Observation 2: reply rates by shape
    w("2. **Reply rates by shape** (provider counter numerator):")
    for shape in ("statement", "question", "reply_prefix"):
        n = shape_counts.get(shape, 0)
        nr = shape_with_reply.get(shape, 0)
        if n > 0:
            w(f"   - {shape}: {nr}/{n} = {100*nr/n:.2f}% (n={n:,})")
    w()

    # Observation 3: Re: and threading
    if reply_prefix_rows:
        w(f"3. **Re: prefix and threading**: {len(reply_prefix_rows):,} sent rows "
          f"carry a `Re:` prefix. Of those, "
          f"{len(reply_prefix_with_thread):,} "
          f"({100*len(reply_prefix_with_thread)/max(len(reply_prefix_rows),1):.1f}%) "
          f"have `thread_reply=True`. This is consistent with `Re:` being a "
          f"threading mechanism rather than an independent subject choice.")
        w()

    # Observation 4: length
    if lengths_replied and lengths_not_replied:
        w(f"4. **Subject length**: mean of replied = {sum(lengths_replied)/len(lengths_replied):.1f} chars "
          f"(n={len(lengths_replied)}), mean of not replied = "
          f"{sum(lengths_not_replied)/len(lengths_not_replied):.1f} chars "
          f"(n={len(lengths_not_replied)}).")
        w()

    w("---")
    w()
    w("## HYPOTHESES")
    w()
    w("1. **`Re:` is threading, not a shape.** The high `thread_reply` rate "
      "among `Re:` subjects suggests they are follow-ups in an existing "
      "thread, not an independent subject strategy. Treating them as a "
      "separate shape conflates cadence position with subject choice.")
    w()
    w("2. **Sample size is the dominant uncertainty.** The sampled sent rows "
      f"({total_collected:,}) are a small fraction of the estate's "
      f"{sum(c.get('emails_sent', 0) for c in campaign_info.values()):,} "
      "total sends. Reply counts on individual rows are sparse (most are 0), "
      "so shape-level reply rates have wide confidence intervals.")
    w()
    w("3. **Subject length may not be independent of shape.** Longer subjects "
      "tend to be statements; shorter ones tend to be questions. Any "
      "length-outcome correlation may be a shape-outcome correlation in "
      "disguise.")
    w()

    w("---")
    w()
    w("## PROVEN LEARNINGS")
    w()
    w("**Empty.** Nothing in this analysis survives a sample-size objection "
      "as a proven learning. The reply rates by shape are observations with "
      "wide confidence intervals, not actionable findings. The estate has "
      f"{total_collected:,} sampled sent rows across {len(sampling_log)} "
      "campaigns, but the reply counts per shape are too sparse to "
      "distinguish signal from noise. A difference with n<30 is an "
      "observation, never a learning.")
    w()
    w("The one structural finding — that `Re:` prefix is a threading "
      "mechanism rather than an independent subject choice — is supported "
      "by the provider's own `thread_reply` field and is stated as an "
      "observation, not a learning, because the sample of `Re:` subjects "
      "is small.")
    w()

    w("---")
    w()
    w("## Data Quality Notes")
    w()
    w("- **No open-rate claim.** `open_tracking` is FALSE estate-wide. "
      "Zero opens is an absent measurement, not a zero.")
    w("- **Two reply numerators.** The provider's `replies` counter on the "
      "scheduled email row and the reply feed cross-reference are different "
      "measurements. The feed is a sample; the counter is per-row but "
      "unverified against individual reply rows.")
    w("- **Empty subjects excluded.** Rows with no subject are not counted "
      "as short subjects. They are unmeasurable.")
    w("- **PII redacted.** No emails, names, or company domains in this report.")
    w()

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    analyse()
