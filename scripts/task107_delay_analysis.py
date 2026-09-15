#!/usr/bin/env python3
"""TASK-107: inter-step delay distribution and time-to-reply investigation.

READS ONLY at both providers. No writes of any kind.

Three questions:
  1. What is the real distribution of configured inter-step delays, per provider?
  2. Is time-to-reply computable from the data the providers carry?
  3. If so, what does the distribution look like?

Caches provider data to .qwen/tmp/task107/ to avoid re-reading the API.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.providers import load_env, key as get_key, request as api_request, query

CACHE_DIR = os.path.join(ROOT, ".qwen", "tmp", "task107")
REPORT_PATH = os.path.join(ROOT, "docs", "DELAY-ANALYSIS-2026-09-15.md")


def ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


def cache_path(name):
    return os.path.join(CACHE_DIR, name)


def load_cache(name):
    p = cache_path(name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_cache(name, data):
    ensure_cache()
    with open(cache_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# --------------------------------------------------------- EmailBison

def bison_headers():
    return {"Authorization": f"Bearer {get_key('BISON_KEY')}"}


def bison_base():
    return os.environ.get("BISON_BASE", "https://send.resonategroup.co/api").rstrip("/")


def bison_get(path, params=None):
    url = f"{bison_base()}{path}"
    if params:
        url = query(url, params)
    status, data = api_request("GET", url, bison_headers())
    if status is None or status < 200 or status >= 300:
        raise RuntimeError(f"GET {path} -> {status}")
    return data if isinstance(data, dict) else {}


def bison_fetch_all_offset(path, params_base=None, max_pages=None):
    rows, page = [], 1
    while True:
        p = dict(params_base or {})
        p["page"] = page
        data = bison_get(path, p)
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        rows.extend(chunk)
        meta = data.get("meta") or {}
        if max_pages and page >= max_pages:
            break
        last = meta.get("last_page")
        try:
            last = int(last)
        except (TypeError, ValueError):
            break
        if page >= last:
            break
        page += 1
        time.sleep(0.1)
    return rows


def bison_fetch_all_cursor(path, per_page=100, max_pages=None):
    rows, cursor, page = [], None, 1
    while True:
        p = {"pagination_type": "cursor", "per_page": per_page}
        if cursor:
            p["cursor"] = cursor
        data = bison_get(path, p)
        chunk = data.get("data")
        if not isinstance(chunk, list) or not chunk:
            break
        rows.extend(chunk)
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        if max_pages and page >= max_pages:
            break
        if not cursor:
            break
        page += 1
        time.sleep(0.1)
    return rows


def collect_bison_campaigns():
    cached = load_cache("bison_campaigns.json")
    if cached is not None:
        print(f"  [bison] {len(cached)} campaigns from cache")
        return cached
    print("  [bison] fetching campaigns...")
    campaigns = bison_fetch_all_offset("/campaigns")
    save_cache("bison_campaigns.json", campaigns)
    print(f"  [bison] {len(campaigns)} campaigns cached")
    return campaigns


def collect_bison_steps(campaigns):
    cached = load_cache("bison_steps.json")
    if cached is not None:
        print(f"  [bison] {len(cached)} steps from cache")
        return cached
    print("  [bison] fetching sequence steps...")
    all_steps = []
    for camp in campaigns:
        cid = camp["id"]
        try:
            data = bison_get(f"/campaigns/{cid}/sequence-steps")
        except RuntimeError:
            continue
        steps = data.get("data")
        if not isinstance(steps, list):
            continue
        for s in steps:
            s["_campaign_id"] = cid
            all_steps.append(s)
        time.sleep(0.1)
    save_cache("bison_steps.json", all_steps)
    print(f"  [bison] {len(all_steps)} steps cached")
    return all_steps


def collect_bison_replies(max_pages=200):
    """Fetch the reply feed. Bounded sample - newest first."""
    cached = load_cache("bison_replies.json")
    if cached is not None:
        print(f"  [bison] {len(cached)} reply rows from cache")
        return cached
    print(f"  [bison] fetching replies (max {max_pages} pages)...")
    replies = bison_fetch_all_cursor("/replies", per_page=100, max_pages=max_pages)
    save_cache("bison_replies.json", replies)
    print(f"  [bison] {len(replies)} reply rows cached")
    return replies


def collect_bison_scheduled_for_time_to_reply(campaigns):
    """Collect scheduled emails with sent_at for campaigns that have sends.

    Bounded: 100 pages per campaign (15 rows/page = up to 1500 rows).
    Only campaigns with emails_sent > 0.
    """
    cached = load_cache("bison_scheduled_ttr.json")
    if cached is not None:
        print(f"  [bison] {len(cached)} scheduled emails from cache")
        return cached
    print("  [bison] fetching scheduled emails for time-to-reply...")
    all_rows = []
    for camp in campaigns:
        cid = camp["id"]
        sent_count = int(camp.get("emails_sent") or 0)
        if sent_count == 0:
            continue
        for page in range(1, 101):
            try:
                data = bison_get(f"/campaigns/{cid}/scheduled-emails",
                                 {"page": page})
            except RuntimeError:
                break
            chunk = data.get("data")
            if not isinstance(chunk, list) or not chunk:
                break
            for se in chunk:
                if se.get("sent_at"):
                    all_rows.append({
                        "id": se.get("id"),
                        "campaign_id": cid,
                        "sent_at": se.get("sent_at"),
                        "scheduled_date": se.get("scheduled_date"),
                        "status": se.get("status"),
                        "sequence_step_id": se.get("sequence_step_id"),
                    })
            meta = data.get("meta") or {}
            try:
                last = int(meta.get("last_page"))
            except (TypeError, ValueError):
                break
            if page >= last:
                break
            time.sleep(0.1)
        print(f"    campaign {cid}: {len([r for r in all_rows if r['campaign_id'] == cid])} sent rows")
        sys.stdout.flush()
    save_cache("bison_scheduled_ttr.json", all_rows)
    print(f"  [bison] {len(all_rows)} scheduled emails with sent_at cached")
    return all_rows


# --------------------------------------------------------- HeyReach

def heyreach_headers():
    return {"X-API-KEY": get_key("HEYREACH_KEY")}


HEYREACH_BASE = "https://api.heyreach.io/api/public"


def heyreach_post(path, body):
    status, data = api_request("POST", f"{HEYREACH_BASE}{path}",
                               heyreach_headers(), body)
    if status is None or status < 200 or status >= 300:
        raise RuntimeError(f"POST {path} -> {status}")
    return data if isinstance(data, dict) else {}


def heyreach_get(path, params=None):
    import urllib.parse
    q = urllib.parse.urlencode(params or {})
    url = f"{HEYREACH_BASE}{path}?{q}"
    status, data = api_request("GET", url, heyreach_headers())
    if status is None or status < 200 or status >= 300:
        raise RuntimeError(f"GET {path} -> {status}")
    return data if isinstance(data, dict) else {}


def collect_heyreach_campaigns():
    cached = load_cache("heyreach_campaigns.json")
    if cached is not None:
        print(f"  [heyreach] {len(cached)} campaigns from cache")
        return cached
    print("  [heyreach] fetching campaigns...")
    all_items = []
    offset = 0
    while True:
        data = heyreach_post("/campaign/GetAll",
                             {"offset": offset, "limit": 100})
        items = data.get("items") or []
        if not isinstance(items, list):
            break
        all_items.extend(items)
        total = data.get("totalCount")
        offset += len(items)
        if not items or (total is not None and offset >= int(total)):
            break
        time.sleep(0.2)
    save_cache("heyreach_campaigns.json", all_items)
    print(f"  [heyreach] {len(all_items)} campaigns cached")
    return all_items


def collect_heyreach_sequences(campaigns):
    """Read each campaign's sequence graph. Read-only GET."""
    cached = load_cache("heyreach_sequences.json")
    if cached is not None:
        print(f"  [heyreach] {len(cached)} sequences from cache")
        return cached
    print("  [heyreach] fetching campaign sequences...")
    sequences = {}
    for camp in campaigns:
        cid = camp.get("id")
        if cid is None:
            continue
        try:
            seq = heyreach_get("/campaign/GetCampaignSequence",
                               {"campaignId": cid})
            sequences[str(cid)] = seq
        except RuntimeError as e:
            print(f"    campaign {cid}: {e}")
        time.sleep(0.2)
    save_cache("heyreach_sequences.json", sequences)
    print(f"  [heyreach] {len(sequences)} sequences cached")
    return sequences


# --------------------------------------------------------- analysis

def parse_delay(delay_str):
    """Parse a HeyReach delay string like '+3D' or '+12H' into hours."""
    if not delay_str or not isinstance(delay_str, str):
        return None
    s = delay_str.strip().upper()
    if s.startswith("+"):
        s = s[1:]
    if s.endswith("D"):
        try:
            return int(s[:-1]) * 24
        except ValueError:
            return None
    if s.endswith("H"):
        try:
            return int(s[:-1])
        except ValueError:
            return None
    if s.endswith("M"):
        try:
            return max(1, int(s[:-1]) // 60)
        except ValueError:
            return None
    return None


def extract_heyreach_delays(sequence):
    """Walk a HeyReach sequence graph and extract delay info per edge.

    Returns a list of {campaign_id, delay_hours, delay_text, from_type, to_type}.
    """
    if not isinstance(sequence, dict):
        return []
    results = []
    _walk_delays(sequence, results)
    return results


def _walk_delays(node, results, depth=0):
    """BFS walk extracting delay nodes and their durations."""
    if not isinstance(node, dict) or depth > 50:
        return
    node_type = str(node.get("nodeType") or "").upper()
    if node_type == "WAIT":
        delay_text = node.get("delay") or node.get("duration") or ""
        hours = parse_delay(str(delay_text))
        results.append({
            "delay_hours": hours,
            "delay_text": str(delay_text),
            "node_type": node_type,
        })
    for key in ("trueBranch", "falseBranch", "nextNode", "childNode",
                "onAccept", "onDecline", "onReply", "onNoReply"):
        child = node.get(key)
        if isinstance(child, dict):
            _walk_delays(child, results, depth + 1)
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    _walk_delays(item, results, depth + 1)


def extract_heyreach_step_delays(sequence):
    """Extract inter-step delays from a HeyReach sequence.

    Returns list of delay values in days (as configured).
    Looks at WAIT nodes and delay fields on contacting nodes.
    """
    if not isinstance(sequence, dict):
        return []
    delays = []
    nodes = _walk_all_nodes(sequence)
    for node in nodes:
        nt = str(node.get("nodeType") or "").upper()
        delay_val = node.get("delay") or node.get("delayInDays") or node.get("waitInDays")
        if delay_val is not None:
            if isinstance(delay_val, (int, float)):
                delays.append({"days": int(delay_val), "node_type": nt,
                               "raw": delay_val})
            elif isinstance(delay_val, str):
                hours = parse_delay(delay_val)
                if hours is not None:
                    delays.append({"days": hours // 24,
                                   "hours": hours,
                                   "node_type": nt,
                                   "raw": delay_val})
    return delays


def _walk_all_nodes(root):
    """BFS walk returning every node dict."""
    if not isinstance(root, dict):
        return []
    nodes, seen = [], set()
    queue = [root]
    while queue:
        node = queue.pop(0)
        if not isinstance(node, dict) or id(node) in seen:
            continue
        seen.add(id(node))
        nodes.append(node)
        for key in ("trueBranch", "falseBranch", "nextNode", "childNode",
                     "onAccept", "onDecline", "onReply", "onNoReply",
                     "payload"):
            child = node.get(key)
            if isinstance(child, dict):
                queue.append(child)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        queue.append(item)
    return nodes


def parse_iso_timestamp(ts):
    """Parse an ISO timestamp string to a datetime object."""
    if not ts or not isinstance(ts, str):
        return None
    ts = ts.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


# --------------------------------------------------------- report

def generate_report(bison_campaigns, bison_steps, bison_replies,
                    bison_scheduled, hr_campaigns, hr_sequences):
    lines = []

    def w(s=""):
        lines.append(s)

    w("# Delay Analysis — 2026-09-15")
    w()
    w("TASK-107. Inter-step delay distribution across the estate, and")
    w("whether time-to-reply is computable from provider data.")
    w()
    w("---")
    w()

    # ===== SECTION 1: EmailBison delay distribution =====
    w("## 1. EmailBison: configured inter-step delays")
    w()
    w("**Source:** `GET /campaigns/{id}/sequence-steps` per campaign.")
    w("**Statement kind:** PROVIDER FACT — `wait_in_days` is the field the API returns.")
    w()

    delay_by_step = defaultdict(Counter)
    campaign_count_by_step = defaultdict(set)
    for s in bison_steps:
        order = s.get("order")
        wait = s.get("wait_in_days")
        cid = s.get("_campaign_id")
        if order is not None and wait is not None:
            delay_by_step[int(order)][int(wait)] += 1
            if cid is not None:
                campaign_count_by_step[int(order)].add(cid)

    w("| Step position | wait_in_days | Campaign count | Step instances |")
    w("|---------------|-------------|----------------|----------------|")
    for step in sorted(delay_by_step.keys()):
        for days in sorted(delay_by_step[step].keys()):
            count = delay_by_step[step][days]
            camps = len(campaign_count_by_step.get(step, set()))
            w(f"| {step} | {days} | {camps} | {count} |")
    w()

    # Aggregate distribution
    all_delays = Counter()
    for s in bison_steps:
        wait = s.get("wait_in_days")
        if wait is not None:
            all_delays[int(wait)] += 1
    total_steps = sum(all_delays.values())

    w("### Aggregate delay distribution (all steps)")
    w()
    w(f"**Total step instances:** {total_steps}")
    w()
    w("| wait_in_days | Count | Share |")
    w("|-------------|-------|-------|")
    for days in sorted(all_delays.keys()):
        count = all_delays[days]
        share = count / total_steps * 100 if total_steps else 0
        w(f"| {days} | {count} | {share:.1f}% |")
    w()

    # Most common delay
    most_common = all_delays.most_common(3)
    if most_common:
        w(f"**Most common delays:** {', '.join(f'{d} days ({c} steps, {c/total_steps*100:.1f}%)' for d, c in most_common)}")
    w()

    # ===== SECTION 2: HeyReach delay distribution =====
    w("## 2. HeyReach: configured inter-step delays")
    w()
    w("**Source:** `GET /campaign/GetCampaignSequence?campaignId=` per campaign.")
    w("**Statement kind:** PROVIDER FACT — delay values from the node graph.")
    w()

    hr_delay_values = Counter()
    hr_delay_by_campaign = defaultdict(list)
    hr_campaigns_with_sequences = 0
    hr_campaigns_with_delays = 0

    for cid_str, seq in hr_sequences.items():
        delays = extract_heyreach_step_delays(seq)
        if delays:
            hr_campaigns_with_delays += 1
        hr_campaigns_with_sequences += 1
        for d in delays:
            days = d.get("days", 0)
            hr_delay_values[days] += 1
            hr_delay_by_campaign[cid_str].append(days)

    w(f"**Campaigns with sequences read:** {hr_campaigns_with_sequences}")
    w(f"**Campaigns with at least one delay node:** {hr_campaigns_with_delays}")
    w()

    if hr_delay_values:
        total_hr = sum(hr_delay_values.values())
        w("| Delay (days) | Count | Share |")
        w("|-------------|-------|-------|")
        for days in sorted(hr_delay_values.keys()):
            count = hr_delay_values[days]
            share = count / total_hr * 100 if total_hr else 0
            w(f"| {days} | {count} | {share:.1f}% |")
        w()
        most_common_hr = hr_delay_values.most_common(3)
        if most_common_hr:
            w(f"**Most common delays:** {', '.join(f'{d} days ({c} instances, {c/total_hr*100:.1f}%)' for d, c in most_common_hr)}")
    else:
        w("No delay nodes found in HeyReach sequences.")
    w()

    # Per-campaign delay summary
    w("### Per-campaign delay profile (HeyReach)")
    w()
    w("| Campaign | Delay sequence (days) |")
    w("|----------|----------------------|")
    for cid_str in sorted(hr_delay_by_campaign.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        delays = hr_delay_by_campaign[cid_str]
        camp_name = ""
        for c in hr_campaigns:
            if str(c.get("id")) == cid_str:
                camp_name = str(c.get("name", ""))[:50]
                break
        w(f"| {cid_str} ({camp_name}) | {', '.join(str(d) for d in delays)} |")
    w()

    # ===== SECTION 3: Combined delay summary =====
    w("## 3. Combined delay summary")
    w()
    w("### EmailBison vs HeyReach delay distributions")
    w()
    all_days = sorted(set(list(all_delays.keys()) + list(hr_delay_values.keys())))
    w("| Delay (days) | EmailBison steps | HeyReach nodes |")
    w("|-------------|-----------------|----------------|")
    for days in all_days:
        bison_count = all_delays.get(days, 0)
        hr_count = hr_delay_values.get(days, 0)
        w(f"| {days} | {bison_count} | {hr_count} |")
    w()

    # ===== SECTION 4: Time-to-reply investigation =====
    w("## 4. Time-to-reply: is it computable?")
    w()
    w("TASK-059 reported: *\"No time-to-reply data available. The 934 matched")
    w("scheduled emails all had status: sent but lacked sent_at timestamps in")
    w("the cached data.\"*")
    w()
    w("This section investigates whether that was a provider limitation or a")
    w("lookup that was not done.")
    w()

    # Check what the reply rows carry
    reply_rows = [r for r in bison_replies
                  if str(r.get("type") or "").lower() in
                  ("untracked reply", "tracked reply", "reply")]
    reply_with_seid = [r for r in reply_rows if r.get("scheduled_email_id")]
    reply_with_date = [r for r in reply_rows
                       if r.get("date_received") or r.get("created_at")]

    w(f"### Reply feed sample")
    w()
    w(f"- **Total reply rows fetched:** {len(bison_replies)}")
    w(f"- **Reply-type rows:** {len(reply_rows)}")
    w(f"- **Reply rows with `scheduled_email_id`:** {len(reply_with_seid)}")
    w(f"- **Reply rows with a timestamp (`date_received` or `created_at`):** {len(reply_with_date)}")
    w()

    # Check what fields reply rows carry
    if reply_rows:
        sample = reply_rows[0]
        ts_fields = [k for k in sample.keys()
                     if "time" in k.lower() or "date" in k.lower()
                     or "at" in k.lower() or "received" in k.lower()]
        w(f"**Timestamp fields on a sample reply row:** {', '.join(ts_fields) if ts_fields else 'NONE FOUND'}")
        w()

    # Check scheduled emails
    sched_with_sent = [s for s in bison_scheduled if s.get("sent_at")]
    w(f"### Scheduled email sample")
    w()
    w(f"- **Total scheduled emails collected (sent_at present):** {len(bison_scheduled)}")
    w(f"- **With `sent_at`:** {len(sched_with_sent)}")
    w()

    # The join
    sched_by_id = {str(s["id"]): s for s in bison_scheduled if s.get("sent_at")}
    ttr_pairs = []
    for r in reply_with_seid:
        seid = str(r.get("scheduled_email_id"))
        if seid in sched_by_id:
            sent_ts = parse_iso_timestamp(sched_by_id[seid]["sent_at"])
            reply_ts = parse_iso_timestamp(
                r.get("date_received") or r.get("created_at"))
            if sent_ts and reply_ts:
                delta = reply_ts - sent_ts
                delta_hours = delta.total_seconds() / 3600
                if delta_hours >= 0:
                    ttr_pairs.append({
                        "scheduled_email_id": seid,
                        "campaign_id": sched_by_id[seid].get("campaign_id"),
                        "sent_at": sched_by_id[seid]["sent_at"],
                        "reply_at": r.get("date_received") or r.get("created_at"),
                        "delta_hours": round(delta_hours, 1),
                        "delta_days": round(delta_hours / 24, 2),
                    })

    w(f"### Time-to-reply join")
    w()
    w(f"- **Reply rows with `scheduled_email_id`:** {len(reply_with_seid)}")
    w(f"- **Matching scheduled email found (with `sent_at`):** {len(ttr_pairs)}")
    w()

    if ttr_pairs:
        w("**VERDICT: TIME-TO-REPLY IS COMPUTABLE.**")
        w()
        w("TASK-059's claim that \"no time-to-reply data available\" was wrong.")
        w("The `sent_at` field IS present on scheduled emails, and the reply row")
        w("carries `date_received`. The join via `scheduled_email_id` produces")
        w(f"{len(ttr_pairs)} computable time-to-reply pairs.")
        w()

        # Distribution
        deltas = [p["delta_hours"] for p in ttr_pairs]
        deltas.sort()
        n = len(deltas)

        w("### Time-to-reply distribution")
        w()
        w(f"**n = {n} reply-to-sent pairs**")
        w()

        # Percentiles
        def percentile(data, p):
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f])

        w("| Statistic | Hours | Days |")
        w("|-----------|-------|------|")
        w(f"| Min | {deltas[0]:.1f} | {deltas[0]/24:.2f} |")
        w(f"| p10 | {percentile(deltas, 10):.1f} | {percentile(deltas, 10)/24:.2f} |")
        w(f"| p25 | {percentile(deltas, 25):.1f} | {percentile(deltas, 25)/24:.2f} |")
        w(f"| Median | {percentile(deltas, 50):.1f} | {percentile(deltas, 50)/24:.2f} |")
        w(f"| p75 | {percentile(deltas, 75):.1f} | {percentile(deltas, 75)/24:.2f} |")
        w(f"| p90 | {percentile(deltas, 90):.1f} | {percentile(deltas, 90)/24:.2f} |")
        w(f"| Max | {deltas[-1]:.1f} | {deltas[-1]/24:.2f} |")
        w(f"| Mean | {sum(deltas)/n:.1f} | {sum(deltas)/n/24:.2f} |")
        w()

        # Bucket distribution
        buckets = Counter()
        for h in deltas:
            d = h / 24
            if d < 1:
                buckets["< 1 day"] += 1
            elif d < 2:
                buckets["1-2 days"] += 1
            elif d < 3:
                buckets["2-3 days"] += 1
            elif d < 4:
                buckets["3-4 days"] += 1
            elif d < 5:
                buckets["4-5 days"] += 1
            elif d < 7:
                buckets["5-7 days"] += 1
            elif d < 14:
                buckets["7-14 days"] += 1
            else:
                buckets["14+ days"] += 1

        bucket_order = ["< 1 day", "1-2 days", "2-3 days", "3-4 days",
                        "4-5 days", "5-7 days", "7-14 days", "14+ days"]
        w("### Time-to-reply bucket distribution")
        w()
        w("| Bucket | Count | Share | Cumulative |")
        w("|--------|-------|-------|------------|")
        cum = 0
        for b in bucket_order:
            count = buckets.get(b, 0)
            cum += count
            share = count / n * 100 if n else 0
            cum_share = cum / n * 100 if n else 0
            w(f"| {b} | {count} | {share:.1f}% | {cum_share:.1f}% |")
        w()

        # Key question: what fraction of replies arrive before day 3?
        before_3d = sum(1 for h in deltas if h < 72)
        w(f"**Replies arriving before day 3:** {before_3d} of {n} "
          f"({before_3d/n*100:.1f}%)")
        w()
        before_1d = sum(1 for h in deltas if h < 24)
        w(f"**Replies arriving before day 1:** {before_1d} of {n} "
          f"({before_1d/n*100:.1f}%)")
        w()

        # Per-campaign breakdown
        by_campaign = defaultdict(list)
        for p in ttr_pairs:
            by_campaign[p["campaign_id"]].append(p["delta_hours"])

        w("### Time-to-reply per campaign")
        w()
        w("| Campaign | n | Median (hours) | Median (days) |")
        w("|----------|---|----------------|---------------|")
        for cid in sorted(by_campaign.keys(), key=lambda x: len(by_campaign[x]),
                          reverse=True):
            vals = sorted(by_campaign[cid])
            med = vals[len(vals)//2] if vals else 0
            w(f"| {cid} | {len(vals)} | {med:.1f} | {med/24:.2f} |")
        w()

    else:
        w("**VERDICT: Time-to-reply is NOT computable from this sample.**")
        w()
        w("Possible reasons:")
        w("- The reply rows with `scheduled_email_id` did not match any")
        w("  scheduled email in the collected sample (pagination limit).")
        w("- The timestamps were not parseable.")
        w()

    # ===== SECTION 5: Observations and Hypotheses =====
    w("## 5. Observations, Hypotheses, and Proven Learnings")
    w()
    w("### Observations (with n)")
    w()
    w(f"- EmailBison estate: {len(bison_campaigns)} campaigns, "
      f"{total_steps} step instances across "
      f"{len(bison_steps)} total step rows.")
    w(f"- EmailBison most common delay: "
      f"{most_common[0][0] if most_common else '?'} days "
      f"({most_common[0][1] if most_common else 0} instances).")
    w(f"- HeyReach estate: {len(hr_campaigns)} campaigns, "
      f"{hr_campaigns_with_sequences} sequences read.")
    if hr_delay_values:
        w(f"- HeyReach most common delay: "
          f"{most_common_hr[0][0] if most_common_hr else '?'} days "
          f"({most_common_hr[0][1] if most_common_hr else 0} instances).")
    if ttr_pairs:
        w(f"- Time-to-reply: {len(ttr_pairs)} computable pairs from "
          f"{len(reply_with_seid)} reply rows with scheduled_email_id.")
        w(f"- Median time-to-reply: {percentile(deltas, 50):.1f} hours "
          f"({percentile(deltas, 50)/24:.2f} days).")
        w(f"- {before_3d/n*100:.1f}% of replies arrive before day 3.")
    w()
    w("### Hypotheses")
    w()
    if ttr_pairs and before_3d / n > 0.5:
        w(f"- A follow-up at day 3 arrives AFTER most replies have already "
          f"arrived ({before_3d/n*100:.1f}% replied before day 3). This "
          f"suggests that the day-3 follow-up window captures the tail of "
          f"the reply distribution, not the bulk.")
    w()
    w("### Proven Learnings")
    w()
    if ttr_pairs:
        w(f"- Time-to-reply IS computable for the {len(ttr_pairs)} matched "
          f"rows. TASK-059's claim that it was not available was wrong — "
          f"the `sent_at` field IS present on scheduled emails and "
          f"`date_received` IS present on reply rows; the join works.")
    else:
        w("- Nothing survives a sample-size objection yet.")
    w()
    w("---")
    w()
    w(f"*Sample: {len(bison_replies)} EmailBison reply rows (cursor-paginated, "
      f"newest first), {len(bison_scheduled)} scheduled emails (first 100 "
      f"pages per campaign, offset pagination at 15 rows/page). "
      f"{hr_campaigns_with_sequences} HeyReach sequences read via "
      f"GetCampaignSequence.*")
    w()
    w("*No unsanitised prospect PII in this report.*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true",
                        help="Collect data from providers")
    parser.add_argument("--analyze", action="store_true",
                        help="Run analysis on cached data")
    parser.add_argument("--both", action="store_true",
                        help="Collect then analyze (default)")
    parser.add_argument("--reply-pages", type=int, default=200,
                        help="Max reply feed pages to fetch (default 200)")
    args = parser.parse_args()

    if not args.collect and not args.analyze:
        args.both = True

    load_env()
    ensure_cache()

    bison_campaigns = []
    bison_steps = []
    bison_replies = []
    bison_scheduled = []
    hr_campaigns = []
    hr_sequences = {}

    if args.collect or args.both:
        print("=== Collecting EmailBison data ===")
        bison_campaigns = collect_bison_campaigns()
        bison_steps = collect_bison_steps(bison_campaigns)
        bison_replies = collect_bison_replies(max_pages=args.reply_pages)
        bison_scheduled = collect_bison_scheduled_for_time_to_reply(
            bison_campaigns)

        print()
        print("=== Collecting HeyReach data ===")
        hr_campaigns = collect_heyreach_campaigns()
        hr_sequences = collect_heyreach_sequences(hr_campaigns)

    if args.analyze or args.both:
        if not bison_campaigns:
            print("Loading cached data...")
            bison_campaigns = collect_bison_campaigns()
            bison_steps = collect_bison_steps(bison_campaigns)
            bison_replies = collect_bison_replies(max_pages=args.reply_pages)
            bison_scheduled = collect_bison_scheduled_for_time_to_reply(
                bison_campaigns)
            hr_campaigns = collect_heyreach_campaigns()
            hr_sequences = collect_heyreach_sequences(hr_campaigns)

        print()
        print("=== Generating report ===")
        report = generate_report(bison_campaigns, bison_steps, bison_replies,
                                 bison_scheduled, hr_campaigns, hr_sequences)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
