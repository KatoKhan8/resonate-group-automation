"""TASK-463: Attribute untraceable_company_claim refusals across causes.

Causes:
1. Copy really is making unsupported claims (specific not in ANY research)
2. Evidence exists but not admitted (specific in refused/unverifiable research)
3. Evidence narrowed underneath copy (specific in admitted pack but fails
   sentence-level binding from TASK-330, or caught by TASK-378 single-digit)
4. CLIENT_SUPPLIED facts stopped licensing claims

Sub-categories for cause 1:
1a. Month-word false positive ("may" as modal verb)
1b. Company name in copy not in pack sentences
1c. Contact title/role extracted as proper noun
1d. Genuine unsupported claim

Read-only. Never calls a provider. Never modifies copylint or packfacts.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import copylint, packfacts

MONTH_WORDS = frozenset([
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"
])

# Common title/role words that get extracted as proper nouns
TITLE_WORDS = frozenset([
    "chief", "officer", "director", "manager", "founder", "owner",
    "president", "vice", "head", "lead", "coordinator", "specialist",
    "engineer", "designer", "strategist", "consultant", "partner",
    "executive", "analyst", "administrator", "superintendent",
])


def load_records(path="work/queue.jsonl"):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def extract_rendered_text(rec):
    """All prospect-facing text from a record's cadence."""
    cadence = rec.get("cadence") or {}
    parts = []
    if isinstance(cadence, dict):
        for contact_key, steps in cadence.items():
            if not isinstance(steps, dict):
                continue
            for step_key, step in steps.items():
                if not isinstance(step, dict):
                    continue
                body = step.get("body") or step.get("note") or step.get("text") or ""
                if body:
                    parts.append(body)
    ps = rec.get("ps") or {}
    if isinstance(ps, dict):
        for v in ps.values():
            if v:
                parts.append(str(v))
    li = rec.get("linkedin") or {}
    if isinstance(li, dict):
        for v in li.values():
            if v:
                parts.append(str(v))
    return "\n".join(parts)


def classify_value_shape(value):
    """What KIND of specific is this? Returns a sub-category label."""
    low = value.lower().strip()

    # Month-word ambiguity: "may" is both a month and a modal verb
    if low in MONTH_WORDS:
        return "month_word_ambiguity"

    # Check if it looks like a company name (proper noun pattern match)
    if re.match(r"^(?:[A-Z][a-z]{2,}\s){1,3}[A-Z][a-z]{2,}$", value):
        # Could be a company name or a title
        words = low.split()
        if any(w in TITLE_WORDS for w in words):
            return "title_or_role"
        return "proper_noun_company_or_entity"

    # Pure number
    if re.match(r"^[\d,.]+$", low):
        return "number"

    # Money
    if re.match(r"^[$€£]", low):
        return "money"

    # Percentage
    if re.match(r"^[\d,.]+%$", low):
        return "percentage"

    # Quoted phrase
    if value.startswith('"') and value.endswith('"'):
        return "quoted_phrase"

    return "other"


def classify_cause(value, pack, rec, unused, company_name=""):
    """Determine which cause(s) make this specific untraceable.

    Returns (causes_set, sub_category).
    """
    token = copylint._norm(value)
    if not token:
        return {1}, "empty"

    sub_cat = classify_value_shape(value)

    # Check CLIENT_SUPPLIED facts (cause 4)
    cs_facts = unused.get("CLIENT_SUPPLIED", [])
    cs_text = copylint._norm(" ".join(str(f.get("snippet") or "") for f in cs_facts))
    in_client_supplied = token in cs_text

    # Check refused/unverifiable research (cause 2)
    refused_facts = unused.get("refused", [])
    unverified_facts = unused.get("unverifiable", [])
    refused_text = copylint._norm(" ".join(
        str(f.get("snippet") or "") for f in refused_facts + unverified_facts))
    in_refused = token in refused_text

    # Check admitted pack sentences (cause 3)
    pack_sents = copylint._pack_sentences(pack)
    in_admitted_sent = any(token in ps for ps in pack_sents)

    # Check full admitted pack text
    admitted_text = copylint.pack_text(pack)
    in_admitted_any = token in admitted_text

    # Check if the value is the company name itself
    company_norm = copylint._norm(company_name)
    is_company_name = (company_norm and
                       (token == company_norm or
                        token in company_norm or
                        company_norm in token))

    causes = set()

    if is_company_name and not in_admitted_sent:
        # Company name in copy but not in pack sentences
        # This is a structural issue: company name is not a pack fact
        causes.add(1)
        sub_cat = "company_name_not_in_pack"
    elif in_client_supplied and not in_admitted_any and not in_refused:
        causes.add(4)
    elif in_refused and not in_admitted_any:
        causes.add(2)
    elif in_admitted_sent:
        # In pack sentences but _traces still rejected it
        causes.add(3)
    elif in_admitted_any:
        # In pack text but not in any sentence
        causes.add(3)
    else:
        causes.add(1)

    return causes, sub_cat


def analyze_record(rec):
    """Full analysis of one record."""
    pack, unused = packfacts.pack_for(rec)
    text = extract_rendered_text(rec)
    company_name = rec.get("company") or ""

    pack_stats = {
        "admitted": len(pack.get("facts", [])),
        "refused": len(unused.get("refused", [])),
        "unverifiable": len(unused.get("unverifiable", [])),
        "client_supplied": len(unused.get("CLIENT_SUPPLIED", [])),
    }

    if not text:
        return {
            "record_id": rec.get("id"),
            "has_copy": False,
            "fires": False,
            "untraceable_values": [],
            "pack_stats": pack_stats,
            "company": company_name,
        }

    untraceable_values = copylint.untraceable(text, pack)
    fires = bool(untraceable_values)

    attributed = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        if not copylint.COMPANY_CLAIM.search(sentence):
            continue
        for value in copylint.specifics_in(sentence):
            pack_sents = copylint._pack_sentences(pack)
            if not copylint._traces(value, pack_sents, sentence):
                causes, sub_cat = classify_cause(
                    value, pack, rec, unused, company_name)
                preview = sentence[:100].replace("\n", " ")
                attributed.append({
                    "value": value,
                    "causes": causes,
                    "sub_category": sub_cat,
                    "sentence_preview": preview,
                })

    return {
        "record_id": rec.get("id"),
        "has_copy": True,
        "fires": fires,
        "untraceable_values": attributed,
        "pack_stats": pack_stats,
        "company": company_name,
    }


def main():
    records = load_records()
    print(f"Loaded {len(records)} records")

    total_with_copy = 0
    total_firing = 0
    cause_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    sub_cat_counts = {}
    cause_combos = {}
    all_values = []
    pack_stats_total = {"admitted": 0, "refused": 0,
                        "unverifiable": 0, "client_supplied": 0}
    records_with_no_admitted = 0
    records_with_only_cs = 0
    records_firing_by_pack_state = {
        "no_pack_at_all": 0,
        "only_client_supplied": 0,
        "has_admitted_but_still_fires": 0,
    }

    for rec in records:
        result = analyze_record(rec)
        ps = result["pack_stats"]
        for k in pack_stats_total:
            pack_stats_total[k] += ps[k]

        if ps["admitted"] == 0:
            records_with_no_admitted += 1
        if ps["admitted"] == 0 and ps["client_supplied"] > 0:
            records_with_only_cs += 1

        if not result["has_copy"]:
            continue
        total_with_copy += 1

        if result["fires"]:
            total_firing += 1
            # Classify by pack state
            if ps["admitted"] == 0 and ps["client_supplied"] == 0:
                records_firing_by_pack_state["no_pack_at_all"] += 1
            elif ps["admitted"] == 0:
                records_firing_by_pack_state["only_client_supplied"] += 1
            else:
                records_firing_by_pack_state["has_admitted_but_still_fires"] += 1

            for item in result["untraceable_values"]:
                for c in item["causes"]:
                    cause_counts[c] += 1
                combo = tuple(sorted(item["causes"]))
                cause_combos[combo] = cause_combos.get(combo, 0) + 1
                sub_cat_counts[item["sub_category"]] = \
                    sub_cat_counts.get(item["sub_category"], 0) + 1
                all_values.append({
                    **item,
                    "record_id": result["record_id"],
                    "company": result["company"],
                })

    print(f"\n=== OVERALL STATS ===")
    print(f"Records with rendered copy: {total_with_copy}")
    print(f"Records firing untraceable_company_claim: {total_firing}")
    if total_with_copy:
        print(f"Firing rate: {total_firing/total_with_copy*100:.1f}%")
    print(f"Records with NO admitted pack facts: {records_with_no_admitted}")
    print(f"  of which have CLIENT_SUPPLIED: {records_with_only_cs}")

    print(f"\n=== PACK FACT TOTALS ===")
    for k, v in sorted(pack_stats_total.items()):
        print(f"  {k}: {v}")

    print(f"\n=== FIRING BY PACK STATE ===")
    for k, v in sorted(records_firing_by_pack_state.items()):
        print(f"  {k}: {v}")

    print(f"\n=== CAUSE ATTRIBUTION ===")
    print(f"Total untraceable specifics found: {len(all_values)}")
    for c in sorted(cause_counts):
        labels = {1: "unsupported", 2: "not_admitted",
                  3: "narrowed", 4: "client_supplied"}
        print(f"  Cause {c} ({labels[c]}): {cause_counts[c]} specifics")

    print(f"\n=== CAUSE COMBINATIONS ===")
    labels = {1: "unsupported", 2: "not_admitted",
              3: "narrowed", 4: "client_supplied"}
    for combo, count in sorted(cause_combos.items(), key=lambda x: -x[1]):
        desc = " + ".join(labels[c] for c in combo)
        print(f"  {desc}: {count}")

    print(f"\n=== SUB-CATEGORY BREAKDOWN ===")
    for cat, count in sorted(sub_cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    print(f"\n=== TOP 20 VALUES BY FREQUENCY ===")
    value_freq = {}
    for item in all_values:
        vnorm = item["value"].lower().strip()
        value_freq[vnorm] = value_freq.get(vnorm, 0) + 1
    for val, count in sorted(value_freq.items(), key=lambda x: -x[1])[:20]:
        sample = ""
        for item in all_values:
            if item["value"].lower().strip() == val:
                sample = item["sentence_preview"][:70]
                break
        print(f"  '{val}': {count}x  e.g. ...{sample}...")

    print(f"\n=== SAMPLE SENTENCES BY SUB-CATEGORY ===")
    for cat in sorted(sub_cat_counts.keys()):
        print(f"\n  --- {cat} ---")
        shown = 0
        for item in all_values:
            if item["sub_category"] == cat and shown < 3:
                print(f"    [{item['record_id']}] {item['sentence_preview'][:90]}")
                shown += 1


if __name__ == "__main__":
    main()
