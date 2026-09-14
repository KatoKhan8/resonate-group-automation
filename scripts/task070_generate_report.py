#!/usr/bin/env python3
"""TASK-070: Generate the findings report from collected data."""
import sqlite3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, ".qwen", "tmp", "task070", "cadence.db")
REPORT = os.path.join(ROOT, "docs", "BISON-CADENCE-FINDINGS-2026-09-14.md")


def pct(n, d):
    return f"{100.0 * n / d:.1f}" if d else "0.0"


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    L = []
    w = L.append

    w("# ESTATE BISON CADENCE FINDINGS — 2026-09-14")
    w("")
    w("TASK-070 analysis of the EmailBison estate. Every number carries its "
      "row count and statement kind.")
    w("")
    w("## Statement Kinds")
    w("")
    w("    PROVIDER FACT            the API returned this field with this value")
    w("    RESONATE RECONSTRUCTION  we derived it from provider data")
    w("    ATTRIBUTION HYPOTHESIS   we believe this reply relates to that touch")
    w("")
    w("## Methodology")
    w("")
    w("- **Sent counts** from `emails_sent` on the campaign row (PROVIDER FACT), "
      "never `meta.total`.")
    w("- **Scheduled emails**: 9,540 sent rows sampled (first 100 pages per "
      "campaign, 15 rows/page, offset pagination).")
    w("- **Replies**: 3,375 rows from the most recent portion of the "
      "cursor-paginated feed (15 rows/page).")
    w("- **Reply feed total**: 270,047 rows (PROVIDER FACT from `meta.total`). "
      "Our sample is 1.25%.")
    w("- **Step resolution**: `sequence_step_id` on scheduled email resolved to "
      "parent step `order` via sequence_steps table (RESONATE RECONSTRUCTION).")
    w("")
    w("---")
    w("")

    # === ESTATE OVERVIEW ===
    w("## ESTATE OVERVIEW")
    w("")
    camps = conn.execute(
        "SELECT * FROM campaigns ORDER BY emails_sent DESC").fetchall()
    w("| id | name | status | emails_sent | total_leads |")
    w("|----|------|--------|-------------|-------------|")
    for c in camps:
        w(f"| {c['id']} | {str(c['name'])[:50]} | {c['status']} | "
          f"{c['emails_sent']} | {c['total_leads']} |")
    w("")
    total_sent = sum(c["emails_sent"] for c in camps)
    w(f"**PROVIDER FACT.** Total `emails_sent` across estate: {total_sent}.")
    w("**PROVIDER FACT.** `open_tracking` is FALSE on every campaign "
      "(verified on all 22). No open-rate claim appears.")
    w("")
    w("---")
    w("")

    # === REPLY FEED CLASSIFICATION ===
    w("## REPLY FEED CLASSIFICATION (from 3,375-row sample)")
    w("")
    w("| Type | Auto | Count | Interested |")
    w("|------|------|-------|-----------|")
    for r in conn.execute("""
        SELECT type, automated_reply, COUNT(*) as cnt, SUM(interested) as interested
        FROM replies GROUP BY type, automated_reply ORDER BY cnt DESC
    """).fetchall():
        auto = "auto" if r["automated_reply"] else "human"
        w(f"| {r['type']} | {auto} | {r['cnt']} | {r['interested']} |")
    w("")

    human = conn.execute("""
        SELECT COUNT(*) as c, SUM(interested) as i FROM replies
        WHERE type IN ('Tracked Reply','Untracked Reply') AND automated_reply=0
    """).fetchone()
    auto_r = conn.execute(
        "SELECT COUNT(*) as c FROM replies WHERE automated_reply=1").fetchone()
    outgoing = conn.execute(
        "SELECT COUNT(*) as c FROM replies WHERE type='Outgoing Email'").fetchone()
    w(f"**PROVIDER FACT.** Human replies in sample: {human['c']} "
      f"(interested: {human['i']}).")
    w(f"Automated replies: {auto_r['c']}. Outgoing (our mail): {outgoing['c']}.")
    w("Feed total: 270,047 rows. Sample: 3,375 (1.25%).")
    w("")
    w("---")
    w("")

    # === Q1: CAMPAIGN-LEVEL REPLY RATES ===
    w("## Q1: CAMPAIGN-LEVEL REPLY RATES")
    w("")
    w("Using `emails_sent` (PROVIDER FACT) as denominator. Reply counts from "
      "the reply sample. The sample covers the most recent replies only.")
    w("")

    camp_replies = {}
    for r in conn.execute("""
        SELECT campaign_id, COUNT(*) as cnt, SUM(interested) as interested
        FROM replies WHERE type IN ('Tracked Reply','Untracked Reply')
        AND automated_reply=0 AND campaign_id IS NOT NULL
        GROUP BY campaign_id
    """).fetchall():
        camp_replies[r["campaign_id"]] = (r["cnt"], r["interested"])

    w("| Campaign | emails_sent | Sample replies | Interested | "
      "Est. reply% (sample) |")
    w("|----------|------------|---------------|-----------"
      "|---------------------|")
    total_sample_replies = 0
    for c in camps:
        cid = c["id"]
        sent = c["emails_sent"]
        if sent == 0:
            continue
        replies, interested = camp_replies.get(cid, (0, 0))
        total_sample_replies += replies
        w(f"| {cid} | {sent} | {replies} | {interested} | "
          f"{pct(replies, sent)}% |")
    w("")
    w(f"Total human replies in sample: {total_sample_replies}.")
    w("")
    w("**RESONATE RECONSTRUCTION.** The sample covers the most recent ~2 months "
      "of the reply feed. Campaigns that finished sending before July 2026 "
      "(262-274, 327-335) may have few or no replies in this window. "
      "Their reply counts are UNDERCOUNTS.")
    w("")
    w("---")
    w("")

    # === Q2: STEP-LEVEL DISTRIBUTION ===
    w("## Q2: STEP-LEVEL SEND DISTRIBUTION")
    w("")
    w("From the 9,540-row scheduled-email sample. Step order resolved from "
      "`sequence_step_id` to parent step `order` (RESONATE RECONSTRUCTION).")
    w("")

    w("| Step order | Sample sent | Share of sample |")
    w("|-----------|------------|-----------------|")
    step_data = conn.execute("""
        SELECT step_order, COUNT(*) as cnt
        FROM scheduled_emails WHERE step_order IS NOT NULL
        GROUP BY step_order ORDER BY step_order
    """).fetchall()
    total_sample = sum(r["cnt"] for r in step_data)
    for r in step_data:
        w(f"| {r['step_order']} | {r['cnt']} | "
          f"{pct(r['cnt'], total_sample)}% |")
    w("")
    w(f"Total sample with step resolution: {total_sample} of 9,540.")
    w("")
    w("---")
    w("")

    # === Q3: STEP-LEVEL REPLY ATTRIBUTION ===
    w("## Q3: STEP-LEVEL REPLY ATTRIBUTION (ATTRIBUTION HYPOTHESIS)")
    w("")
    w("Human replies from the sample joined to the scheduled-email sample via "
      "`scheduled_email_id`. This is an ATTRIBUTION HYPOTHESIS.")
    w("")

    attr = conn.execute("""
        SELECT se.step_order, COUNT(*) as cnt, SUM(r.interested) as interested
        FROM replies r
        JOIN scheduled_emails se ON r.scheduled_email_id = se.id
        WHERE r.type IN ('Tracked Reply','Untracked Reply')
        AND r.automated_reply=0 AND se.step_order IS NOT NULL
        GROUP BY se.step_order ORDER BY se.step_order
    """).fetchall()

    total_attr = sum(r["cnt"] for r in attr)
    if attr:
        w("| Reply step (ATTR.HYP.) | Replies | Interested | Share |")
        w("|------|------|-----------|-------|")
        for r in attr:
            w(f"| {r['step_order']} | {r['cnt']} | {r['interested']} | "
              f"{pct(r['cnt'], total_attr)}% |")
        w("")
        w(f"Total attributed replies: {total_attr} "
          f"(of {human['c']} human replies = {pct(total_attr, human['c'])}%).")
        no_attr = human["c"] - total_attr
        w(f"Unattributed (scheduled email not in our sample): {no_attr}.")
    else:
        w("No replies matched the scheduled-email sample.")
    w("")
    w("---")
    w("")

    # === Q4: CADENCE DELAYS ===
    w("## Q4: CADENCE DELAYS AND DURATION")
    w("")
    w("**PROVIDER FACT.** `wait_in_days` per step position.")
    w("")

    w("| Step position | wait_in_days | Campaigns |")
    w("|---------------|-------------|-----------|")
    for r in conn.execute("""
        SELECT step_order, wait_in_days, COUNT(*) as cnt
        FROM sequence_steps WHERE step_order IS NOT NULL AND is_variant=0
        GROUP BY step_order, wait_in_days ORDER BY step_order, wait_in_days
    """).fetchall():
        w(f"| {r['step_order']} | {r['wait_in_days']} | {r['cnt']} |")
    w("")

    w("### Cadence duration per campaign")
    w("")
    w("| Campaign | Parent steps | Total days | Max step |")
    w("|----------|-------------|-----------|---------|")
    for r in conn.execute("""
        SELECT campaign_id, COUNT(*) as steps,
               SUM(wait_in_days) as days, MAX(step_order) as mx
        FROM sequence_steps WHERE is_variant=0
        GROUP BY campaign_id ORDER BY days DESC
    """).fetchall():
        w(f"| {r['campaign_id']} | {r['steps']} | {r['days']} | {r['mx']} |")
    w("")
    w("---")
    w("")

    # === Q5: VARIANT ANALYSIS ===
    w("## Q5: VARIANT-LEVEL DATA (CAMPAIGN 352)")
    w("")
    w("**PROVIDER FACT.** Campaign 352 has 44 sequence steps: 5 parents + "
      "39 variants. Each variant is a first-class step (verdict D, TASK-069).")
    w("")

    w("| Variant id | Parent order | In sample | Replies (ATTR.HYP.) |")
    w("|-----------|-------------|-----------|-------|")
    for r in conn.execute("""
        SELECT ss.id, vs.step_order as parent_order,
            (SELECT COUNT(*) FROM scheduled_emails
             WHERE sequence_step_id=ss.id) as in_sample,
            (SELECT COUNT(*) FROM replies r
             JOIN scheduled_emails se ON r.scheduled_email_id=se.id
             WHERE se.sequence_step_id=ss.id
             AND r.type IN ('Tracked Reply','Untracked Reply')
             AND r.automated_reply=0) as replies
        FROM sequence_steps ss
        LEFT JOIN sequence_steps vs ON ss.variant_from_step = vs.id
        WHERE ss.is_variant=1 ORDER BY vs.step_order, ss.id
    """).fetchall():
        w(f"| {r['id']} | {r['parent_order']} | {r['in_sample']} | "
          f"{r['replies']} |")
    w("")
    w("---")
    w("")

    # === Q6: COPY SHAPE ===
    w("## Q6: COPY SHAPE (FROM SAMPLE)")
    w("")
    w("### Subject-line patterns (top 20)")
    w("")
    subj = conn.execute("""
        SELECT email_subject, COUNT(*) as cnt FROM scheduled_emails
        WHERE email_subject IS NOT NULL
        GROUP BY email_subject ORDER BY cnt DESC LIMIT 20
    """).fetchall()
    w("| Subject (truncated) | Count | Pattern |")
    w("|---------------------|-------|---------|")
    for r in subj:
        s = str(r["email_subject"] or "")[:60]
        if s.rstrip().endswith("?"):
            p = "question"
        elif any(x in s.lower() for x in ["following up", "follow up", "checking"]):
            p = "follow-up"
        elif s.lower().startswith("re:"):
            p = "thread"
        else:
            p = "statement"
        w(f"| {s} | {r['cnt']} | {p} |")
    w("")

    q_count = 0
    s_count = 0
    for r in conn.execute("""
        SELECT email_subject, COUNT(*) as cnt FROM scheduled_emails
        GROUP BY email_subject
    """).fetchall():
        if str(r["email_subject"] or "").rstrip().endswith("?"):
            q_count += r["cnt"]
        else:
            s_count += r["cnt"]
    w(f"Question-led subjects: {q_count} ({pct(q_count, total_sample)}%)")
    w(f"Statement-led subjects: {s_count} ({pct(s_count, total_sample)}%)")
    w("")
    w("---")
    w("")

    # === Q7: 8.49% RE-DERIVATION ===
    w("## RE-DERIVATION: THE 8.49% CLAIM")
    w("")
    w('An earlier session recorded "8-step email sequences reply at 8.49% '
      '(n=17,690)". Re-deriving from `emails_sent` (PROVIDER FACT) and '
      "reply sample.")
    w("")

    camp_max = {}
    for r in conn.execute("""
        SELECT campaign_id, MAX(step_order) as mx FROM sequence_steps
        WHERE is_variant=0 GROUP BY campaign_id
    """).fetchall():
        camp_max[r["campaign_id"]] = r["mx"]

    by_steps = {}
    for c in camps:
        cid = c["id"]
        sent = c["emails_sent"]
        if sent == 0:
            continue
        mx = camp_max.get(cid)
        if mx is None:
            continue
        replies = camp_replies.get(cid, (0, 0))[0]
        if mx not in by_steps:
            by_steps[mx] = {"campaigns": 0, "sent": 0, "replies": 0}
        by_steps[mx]["campaigns"] += 1
        by_steps[mx]["sent"] += sent
        by_steps[mx]["replies"] += replies

    w("| Max steps | Campaigns | emails_sent | Sample replies | "
      "Reply% (sample) |")
    w("|-----------|-----------|-------------|---------------|"
      "-----------------|")
    found = False
    for steps in sorted(by_steps):
        d = by_steps[steps]
        rate = pct(d["replies"], d["sent"])
        mark = ""
        if "8.3" <= rate <= "8.7":
            mark = " <-- near 8.49%"
            found = True
        w(f"| {steps} | {d['campaigns']} | {d['sent']} | "
          f"{d['replies']} | {rate}%{mark} |")
    w("")
    if not found:
        w("**The 8.49% figure was NOT reproduced.** The reply sample covers "
          "only the most recent ~2 months. Campaigns that finished before "
          "July 2026 have their replies outside the sample window. The true "
          "reply rate for older campaigns cannot be determined from this "
          "sample alone.")
        w("")
        w("To fully re-derive this claim, the complete reply feed (270,047 "
          "rows) must be collected and classified. At 15 rows/page and "
          "~1.5s/page, this requires ~18,000 pages and ~7.5 hours of "
          "collection time.")
    w("")
    w("---")
    w("")

    # === CAVEATS ===
    w("## CAVEATS AND DISCIPLINE")
    w("")
    w("1. **Sent counts from `emails_sent`, never `meta.total`.** Campaign 274 "
      "has 30,411 scheduled rows and ZERO of its first 100 pages carry "
      "`sent_at`.")
    w("2. **Reply sample is 1.25% of the feed** (3,375 of 270,047). It covers "
      "the most recent ~2 months only. Older campaign replies are NOT in "
      "the sample.")
    w("3. **Classified the reply feed.** Auto-replies and outgoing mail "
      "excluded from human counts.")
    w("4. **No open-rate claim.** `open_tracking` is False on every campaign.")
    w("5. **Every causal statement is an ATTRIBUTION HYPOTHESIS.**")
    w("6. **`interested` as positive proxy.** Not a classifier verdict — "
      "TASK-067's thread-context classifier has not been run.")
    w("7. **Campaign 274 and 263**: 0 sent rows in first 100 pages. Their "
      "sends are deeper in the pagination. Step-level data for these "
      "campaigns is ABSENT.")
    w("8. **Sample size discipline.** n<30 differences are OBSERVATIONS, "
      "not PROVEN LEARNINGS.")
    w("")
    w("---")
    w("")
    w("*Generated by `scripts/task070_generate_report.py`. "
      "Data in `.qwen/tmp/task070/cadence.db`. "
      "Collection script: `scripts/bison_cadence_analysis.py`.*")

    report = "\n".join(L)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report: {len(report)} chars, {len(L)} lines")
    print(f"Written to: {REPORT}")
    conn.close()


if __name__ == "__main__":
    main()
