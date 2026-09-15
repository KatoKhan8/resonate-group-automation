#!/usr/bin/env python3
"""TASK-107: analyze inter-step delays and time-to-reply availability.

Reads only at both providers. No writes, no sends, no campaign mutations.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers import bison, heyreach


def extract_heyreach_delays(node, delays=None):
    """Recursively extract delays from HeyReach sequence tree."""
    if delays is None:
        delays = []
    
    if not isinstance(node, dict):
        return delays
    
    delay_value = node.get('actionDelay')
    delay_unit = node.get('actionDelayUnit', 'HOUR')
    
    if delay_value is not None:
        if delay_unit == 'HOUR':
            delays.append(('HOUR', delay_value))
        elif delay_unit == 'DAY':
            delays.append(('DAY', delay_value))
    
    if 'conditionalNode' in node:
        extract_heyreach_delays(node['conditionalNode'], delays)
    if 'unconditionalNode' in node:
        extract_heyreach_delays(node['unconditionalNode'], delays)
    
    return delays


def analyze_heyreach_delays():
    """Extract inter-step delays from all HeyReach campaigns."""
    print("=== HeyReach Delay Analysis ===\n")
    
    campaigns_data = heyreach.campaigns()
    if isinstance(campaigns_data, tuple):
        campaigns = campaigns_data[0] if campaigns_data else []
    else:
        campaigns = campaigns_data or []
    
    print(f"Found {len(campaigns)} HeyReach campaigns\n")
    
    delay_distribution = defaultdict(int)
    campaign_delays = []
    
    for campaign in campaigns:
        cid = campaign.get('id')
        name = campaign.get('name', 'unnamed')
        
        try:
            sequence = heyreach.campaign_sequence(cid)
        except Exception:
            continue
        
        if not sequence or not isinstance(sequence, dict):
            continue
        
        delays = extract_heyreach_delays(sequence)
        
        if delays:
            delay_strings = []
            for unit, value in delays:
                delay_str = f"+{value}{unit[0]}"
                delay_strings.append(delay_str)
                delay_distribution[delay_str] += 1
            
            campaign_delays.append({
                'campaign_id': cid,
                'campaign_name': name,
                'delays': delays,
                'delay_strings': delay_strings
            })
    
    print(f"Delay distribution (across all campaigns):")
    for delay_str, count in sorted(delay_distribution.items()):
        print(f"  {delay_str:>6}: {count:>4} occurrences")
    
    print(f"\nCampaigns with delays: {len(campaign_delays)}")
    for cd in campaign_delays[:5]:
        print(f"  Campaign {cd['campaign_id']} ({cd['campaign_name'][:50]}):")
        print(f"    Delays: {', '.join(cd['delay_strings'][:15])}")
    
    return delay_distribution, campaign_delays


def analyze_bison_delays():
    """Extract inter-step delays from all EmailBison campaigns."""
    print("\n=== EmailBison Delay Analysis ===\n")
    
    status, data = bison.request("GET", f"{bison.base()}/campaigns", bison.headers())
    if not bison.ok(status):
        print(f"Could not fetch campaigns: {status}")
        return {}, []
    
    campaigns = data.get('data', [])
    print(f"Found {len(campaigns)} EmailBison campaigns\n")
    
    delay_distribution = defaultdict(int)
    campaign_delays = []
    
    for campaign in campaigns:
        cid = campaign.get('id')
        name = campaign.get('name', 'unnamed')
        
        try:
            steps = bison.sequence_steps(cid)
            if not steps:
                continue
            
            delays = []
            for step in steps:
                wait_days = step.get('wait_in_days')
                if wait_days is not None:
                    delays.append(wait_days)
                    delay_distribution[f"+{wait_days}D"] += 1
            
            if delays:
                campaign_delays.append({
                    'campaign_id': cid,
                    'campaign_name': name,
                    'delays': delays
                })
        except Exception:
            continue
    
    print(f"Delay distribution (across all campaigns):")
    for delay_str, count in sorted(delay_distribution.items()):
        print(f"  {delay_str:>6}: {count:>4} occurrences")
    
    print(f"\nCampaigns with delays: {len(campaign_delays)}")
    for cd in campaign_delays[:5]:
        print(f"  Campaign {cd['campaign_id']} ({cd['campaign_name'][:50]}):")
        print(f"    Delays (days): {', '.join(str(d) for d in cd['delays'])}")
    
    return delay_distribution, campaign_delays


def check_time_to_reply():
    """Check if time-to-reply is computable and compute distribution."""
    print("\n=== Time-to-Reply Analysis ===\n")
    
    # Fetch campaigns
    status, data = bison.request("GET", f"{bison.base()}/campaigns", bison.headers())
    if not bison.ok(status):
        print(f"Could not fetch campaigns: {status}")
        return False
    
    campaigns = data.get('data', [])
    print(f"Found {len(campaigns)} campaigns\n")
    
    # Check structure from first campaign with data
    print("Checking data structure...")
    for campaign in campaigns[:2]:
        cid = campaign.get('id')
        try:
            scheduled = bison.scheduled_emails(cid)
            if scheduled:
                sample_email = scheduled[0]
                print(f"  Email has sent_at: {'sent_at' in sample_email}")
                print(f"  Email has id: {'id' in sample_email}")
                break
        except Exception:
            continue
    
    # Check replies structure
    try:
        rows, _ = bison.fetch_replies(cursor=None)
        if rows:
            sample_reply = rows[0]
            has_date_received = 'date_received' in sample_reply
            has_scheduled_email_id = 'scheduled_email_id' in sample_reply
            print(f"  Reply has date_received: {has_date_received}")
            print(f"  Reply has scheduled_email_id: {has_scheduled_email_id}")
            
            if has_scheduled_email_id and has_date_received:
                print("\n  [YES] TIME-TO-REPLY IS COMPUTABLE")
            else:
                print("\n  [NO] TIME-TO-REPLY NOT COMPUTABLE")
                return False
    except Exception as e:
        print(f"  Could not fetch replies: {e}")
        return False
    
    # Compute distribution from sample of 3 campaigns
    print("\n=== Computing Time-to-Reply Distribution (sample) ===\n")
    
    email_sent_times = {}
    for campaign in campaigns[:3]:
        cid = campaign.get('id')
        try:
            scheduled = bison.scheduled_emails(cid)
            for email in scheduled:
                email_id = email.get('id')
                sent_at = email.get('sent_at')
                if email_id and sent_at:
                    email_sent_times[email_id] = sent_at
        except Exception:
            continue
    
    print(f"Collected {len(email_sent_times)} emails with sent_at (from 3 campaigns)\n")
    
    if not email_sent_times:
        print("No emails with sent_at found")
        return True
    
    # Fetch replies (5 pages)
    replies = []
    cursor = None
    for _ in range(5):
        rows, next_cursor = bison.fetch_replies(cursor=cursor)
        if not rows:
            break
        replies.extend(rows)
        cursor = next_cursor
        if not cursor:
            break
    
    print(f"Fetched {len(replies)} replies\n")
    
    # Compute time-to-reply
    time_to_reply_hours = []
    matched = 0
    
    for reply in replies:
        scheduled_email_id = reply.get('scheduled_email_id')
        date_received = reply.get('date_received')
        
        if not scheduled_email_id or not date_received:
            continue
        
        if scheduled_email_id not in email_sent_times:
            continue
        
        sent_at = email_sent_times[scheduled_email_id]
        
        try:
            sent_dt = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
            received_dt = datetime.fromisoformat(date_received.replace('Z', '+00:00'))
            delta_hours = (received_dt - sent_dt).total_seconds() / 3600
            
            if delta_hours >= 0:
                time_to_reply_hours.append(delta_hours)
                matched += 1
        except Exception:
            continue
    
    print(f"Matched replies: {matched}\n")
    
    if not time_to_reply_hours:
        print("No time-to-reply data computable from this sample")
        return True
    
    # Distribution
    time_to_reply_hours.sort()
    
    print("Time-to-reply distribution:")
    buckets = [
        (0, 1, "< 1h"),
        (1, 6, "1-6h"),
        (6, 24, "6-24h"),
        (24, 48, "1-2 days"),
        (48, 72, "2-3 days"),
        (72, 120, "3-5 days"),
        (120, 168, "5-7 days"),
        (168, float('inf'), "> 7 days")
    ]
    
    for low, high, label in buckets:
        count = sum(1 for t in time_to_reply_hours if low <= t < high)
        pct = (count / len(time_to_reply_hours)) * 100
        print(f"  {label:>12}: {count:>4} ({pct:>5.1f}%)")
    
    avg = sum(time_to_reply_hours) / len(time_to_reply_hours)
    median = time_to_reply_hours[len(time_to_reply_hours) // 2]
    print(f"\nAverage: {avg:.1f} hours ({avg/24:.1f} days)")
    print(f"Median: {median:.1f} hours ({median/24:.1f} days)")
    
    before_day_3 = sum(1 for t in time_to_reply_hours if t < 72)
    pct_before_day_3 = (before_day_3 / len(time_to_reply_hours)) * 100
    print(f"\nReplies before day 3: {before_day_3} ({pct_before_day_3:.1f}%)")
    
    return True


def main():
    print("TASK-107: Inter-step delay and time-to-reply analysis")
    print("=" * 70)
    
    analyze_heyreach_delays()
    analyze_bison_delays()
    check_time_to_reply()
    
    print("\n" + "=" * 70)
    print("Analysis complete")


if __name__ == "__main__":
    main()
