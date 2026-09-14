#!/usr/bin/env python3
"""Measure punctuation failures across the estate fixtures.

TASK-055 measurement: how often is punctuation the reason for rejection,
and does the next attempt pass?
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import lint, events


def measure():
    fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'tests', 'fixtures')
    all_rejected = []
    all_lint_failed_events = []

    for fname in sorted(os.listdir(fixtures_dir)):
        if not fname.endswith('.jsonl'):
            continue
        path = os.path.join(fixtures_dir, fname)
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                # Check log entries for rejected drafts
                for entry in rec.get('log', []):
                    if entry.get('rejected'):
                        for r in entry['rejected']:
                            all_rejected.append({
                                'fixture': fname,
                                'step': entry.get('step'),
                                'reason': r,
                                'record': rec.get('id')
                            })
                # Check events for LINT_FAILED
                for ev in rec.get('events', []):
                    if ev.get('type') == events.LINT_FAILED:
                        all_lint_failed_events.append({
                            'fixture': fname,
                            'record': rec.get('id'),
                            'step': ev.get('step'),
                            'failures': ev.get('failures', []),
                            'attempt': ev.get('attempt')
                        })

    print(f"Total rejected log entries: {len(all_rejected)}")
    print(f"Total LINT_FAILED events: {len(all_lint_failed_events)}")
    print()

    # Break down rejected entries by reason
    reason_counts = Counter()
    punct_rejected = []
    for r in all_rejected:
        reason = r['reason']
        # Check if it mentions punctuation-related issues
        is_punct = (any(c in reason for c in lint.SUBSTITUTED_PUNCTUATION)
                    or 'em dash' in reason.lower()
                    or 'curly' in reason.lower()
                    or 'apostrophe' in reason.lower()
                    or 'non-breaking' in reason.lower()
                    or 'plain ascii' in reason.lower())
        if is_punct:
            punct_rejected.append(r)
        reason_counts[reason[:80]] += 1

    print("Punctuation-related rejections:")
    for r in punct_rejected:
        print(f"  {r['fixture']} / {r['record']} / {r['step']}: {r['reason'][:100]}")
    print(f"Total punctuation rejections: {len(punct_rejected)}")
    print()

    # Break down LINT_FAILED events by failure type
    failure_counts = Counter()
    punct_events = []
    for ev in all_lint_failed_events:
        for f in ev['failures']:
            failure_counts[f] += 1
        if 'em_dash' in ev['failures']:
            punct_events.append(ev)

    print("LINT_FAILED failure breakdown:")
    for f, c in failure_counts.most_common():
        print(f"  {f}: {c}")
    print()
    print(f"Events with em_dash: {len(punct_events)}")
    for ev in punct_events:
        print(f"  {ev['fixture']} / {ev['record']} / {ev['step']} / attempt {ev['attempt']}: {ev['failures']}")
    print()

    # Now check: when a draft fails on punctuation alone, does the NEXT attempt pass?
    # Group events by (record, step) and sort by attempt
    by_record_step = defaultdict(list)
    for ev in all_lint_failed_events:
        key = (ev['record'], ev['step'])
        by_record_step[key].append(ev)

    print("Retry analysis: when punctuation fails, what happens on the next attempt?")
    punct_only_sequences = []
    for (rec, step), evts in sorted(by_record_step.items()):
        evts.sort(key=lambda e: e.get('attempt', 0))
        for i, ev in enumerate(evts):
            if 'em_dash' in ev['failures']:
                # Check if this was punctuation-only
                other_failures = [f for f in ev['failures'] if f != 'em_dash']
                if not other_failures:
                    # Punctuation-only failure
                    if i + 1 < len(evts):
                        next_ev = evts[i + 1]
                        passed = 'em_dash' not in next_ev['failures']
                        punct_only_sequences.append({
                            'record': rec,
                            'step': step,
                            'attempt': ev['attempt'],
                            'next_attempt': next_ev['attempt'],
                            'next_passed': passed,
                            'next_failures': next_ev['failures']
                        })
                    else:
                        # No next attempt in events - check if draft was ultimately stored
                        punct_only_sequences.append({
                            'record': rec,
                            'step': step,
                            'attempt': ev['attempt'],
                            'next_attempt': None,
                            'next_passed': None,
                            'next_failures': None
                        })

    print(f"Punctuation-only failure sequences: {len(punct_only_sequences)}")
    for seq in punct_only_sequences:
        status = "PASS" if seq['next_passed'] else ("FAIL" if seq['next_passed'] is False else "NO_RETRY")
        print(f"  {seq['record']} / {seq['step']} / attempt {seq['attempt']} -> {status}")
        if seq['next_failures'] is not None:
            print(f"    Next attempt failures: {seq['next_failures']}")


if __name__ == '__main__':
    measure()
