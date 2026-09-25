"""The anchor, per batch, at whichever snippet cap you ask for.

LANE O, 2026-09-25. **Nothing here crawls, spends or sends.** It reads a
crawl log written by `scripts/researchpack_us_crawl.py` and reports the five
numbers the operator asked for, per batch, with the denominator every time:

    domains crawled
    with a usable fact
    passing rule 1
    resting on ONE word
    MEDIAN ANCHOR LENGTH

## WHY THE ANCHOR AND NOT THE PASS RATE

Rule 1 asks whether any opener token over four characters appears anywhere in
the pack. A long dump of a company's prose answers that by accident: lane K
measured 1,496 of 4,478 passes resting on a single word and `marketing` in
579 of them, because 10,565 of the 12,407 contacts are Marketing &
Advertising, the opener puts `{sector}` in its first line, and the site says
it back. **The word tracks the SIC code, which is the proof it is not
research.** Lane H measured the same thing from the other end: before its
re-render the longest contiguous phrase any of 128 openers shared with its
own pack was three words and not one reached four; after, every one was >=7.

So a pass rate that rises while the anchor does not has not worked, and this
module reports the anchor first.

## TWO ANCHORS, BECAUSE THIS COHORT HAS NO RENDERED COPY

`anchor_template` is the anchor of the opener production renders TODAY -
`cadence.TEMPLATES["persona_pain"]` with `template_vars`, which is what lane
K projected rule 1 against. It is bounded by what a template can share with a
site and it is near 1 by construction. Raising the snippet cap cannot move it
much and this module does not pretend otherwise.

`anchor_grounded` is the anchor of the opener lane H's renderer WOULD write:
it is the length of the quotable span `grounded_fact` finds on the site,
because lane H's step 1 quotes that span verbatim and the anchor is therefore
the quote. **This is where a longer snippet pays.** Lane H held 103 of its
128 leads, 52 for "no quotable span on any admitted page" and 31 for "no site
page admitted to this pack" - both of which are what a 400-character
navigation bar looks like from the renderer's side.

Reporting one without the other would be a report that agrees with itself.

## NOTHING HERE RESTATES ANOTHER LANE'S MATCHING

`anchor_run`, `grounded_fact` and `_strip_nav` are LANE H's, materialised
from lane H's own git blob at run time and the sha printed, the way lane K
materialised lane C's `site.py`. `openers_for` and `rule1_tokens` are LANE
K's, imported from `scripts/researchpack_us_rule1.py`. `pack_text`,
`first_line` and `_WORD` are production's `copylint` - the gate itself. A
second copy of any of them would be a number that agrees with this file and
not with the system.

## THE CAP IS APPLIED HERE, TO THE STORED SNIPPET

`--cap 400 --cap 2000` re-truncates the SAME rows, so the comparison is one
crawl, one set of pages, one variable. Comparing against lane K's 400-char
log instead would also vary the hour, the DNS, and which sites were up.

## AND published_at IS NULL ON EVERY FACT BY DESIGN

Source and snippet are per fact; the DATE is `retrieved_at` at PACK level,
because a crawled page carries no publication date worth trusting and
stamping one would make every site fact read as published today. A QA check
that reads "source, date and snippet" per fact refuses all 14,491 of them.
It has to read the date at pack level. Said here because this is the file
that counts them.
"""
import argparse
import collections
import importlib.util
import json
import os
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if os.path.join(HERE, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(HERE, "scripts"))

from src import clients, copylint                              # noqa: E402
import researchpack_us_rule1 as lanek                          # noqa: E402
import researchpack_us_crawl as crawl                          # noqa: E402

#: Lane H's branch and the file the anchor comes from, unchanged.
LANE_H_BRANCH = "worktree-agent-a1c6f33167025b67f"
LANE_H_FILE = "scripts/lane_h_pack_grounded_render.py"


def lane_h(repo, branch=LANE_H_BRANCH, path=LANE_H_FILE):
    """Lane H's render module from its blob. Returns `(module, blob_sha)`.

    Materialised rather than copied for the reason lane K gave about lane
    C's `site.py`: a copy in this tree is a fork somebody later edits, and
    then the anchor this lane reports and the anchor lane H reports drift
    apart without either number changing its name.
    """
    sha = subprocess.run(["git", "rev-parse", "%s:%s" % (branch, path)],
                         cwd=repo, capture_output=True, text=True,
                         check=True).stdout.strip()
    body = subprocess.run(["git", "cat-file", "blob", sha], cwd=repo,
                          capture_output=True, check=True).stdout
    target = os.path.join(repo, "work", "laneh-render-%s.py" % sha[:12])
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as handle:
        handle.write(body)
    name = "laneh_render_blob"
    spec = importlib.util.spec_from_file_location(name, target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module, sha


# --------------------------------------------------------- menu density

def nav_words(snippet):
    """How many of lane K's menu words this snippet contains.

    A COUNT IS THE WRONG STATISTIC ACROSS TWO CAPS and it took one run to
    see it: `lanek.navigation_led` fires at three menu words anywhere in the
    snippet, so a 2000-character snippet trips it more often than a 400 one
    while carrying FIVE TIMES the prose - the metric went 83.5% to 94.1% and
    read as the cap making things worse. Lane K's own probe measured
    DENSITY, menu words per 400 characters, and it fell 4.16 -> 1.47. That
    is the comparable number and it is what this reports. The boolean is
    kept beside it, labelled as a boolean, because it is the number lane K's
    400-char report published and a reader will look for it.
    """
    low = " %s " % str(snippet or "").lower()
    return sum(low.count(" %s " % w) for w in lanek.NAV_WORDS)


# ------------------------------------------------------------- the rows

def read_log(path):
    """domain -> row, last write wins so a resumed log reads as one run."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("domain"):
                rows[row["domain"]] = row
    return rows


def capped(row, cap):
    """The same row with every snippet re-truncated to `cap` characters.

    `facts.clean` has already collapsed whitespace, so slicing here is the
    same operation the crawler would have done with that cap set - and the
    `fact_id` is untouched because `facts.fact_id` hashes `clean(snippet,
    200)` with an EXPLICIT limit. A draft that cited the 400-char fact still
    traces to the 2000-char one.
    """
    if not cap:
        return row
    out = []
    for fact in row.get("facts") or []:
        fact = dict(fact)
        fact["snippet"] = str(fact.get("snippet") or "")[:cap]
        out.append(fact)
    return dict(row, facts=out)


# -------------------------------------------------------- one domain, one cap

def measure_domain(row, config, lh, english_only=True):
    """Every number this report needs about one domain at one cap."""
    out = {"domain": row.get("domain"),
           "contacts": int(row.get("contacts") or 1),
           "outcome": row.get("outcome"),
           "facts": len(row.get("facts") or []),
           "nav_facts": 0, "nav_words": 0, "snippet_chars": 0,
           "rule1": False, "matched": [],
           "anchor_template": 0, "anchor_grounded": 0,
           "quote": None, "hold": None}
    facts = row.get("facts") or []
    for fact in facts:
        if lanek.navigation_led(fact.get("snippet")):
            out["nav_facts"] += 1
        out["nav_words"] += nav_words(fact.get("snippet"))
        out["snippet_chars"] += len(str(fact.get("snippet") or ""))
    if not facts:
        out["hold"] = "no usable fact"
        return out

    pack = {"facts": facts}
    supported = copylint.pack_text(pack)

    # RULE 1 AND THE TEMPLATE ANCHOR, off lane K's own projected openers.
    best_hits, best_anchor = [], 0
    openers = lanek.openers_for(row, config)
    if not openers:
        out["hold"] = "no renderable opener"
    for _persona, _angle, opener in openers:
        hits = lanek.matched(lanek.rule1_tokens(opener, True), supported)
        if len(hits) > len(best_hits):
            best_hits = hits
        run, _span = lh.anchor_run(opener, pack, copylint)
        best_anchor = max(best_anchor, run)
    # The THINNEST angle is what lane K reported for the single-word count,
    # because which angle a contact gets is decided by their title and no
    # title is known here. Kept as the headline for the same reason.
    thin = None
    for _persona, _angle, opener in openers:
        hits = lanek.matched(lanek.rule1_tokens(opener, True), supported)
        if hits and (thin is None or len(hits) < len(thin)):
            thin = hits
    out["rule1"] = bool(thin)
    out["matched"] = thin or []
    out["anchor_template"] = best_anchor

    # THE GROUNDED ANCHOR: the span lane H's renderer would quote. Its word
    # count IS the anchor, because the opener carries the span verbatim.
    try:
        fact, reason, _seen = lh.grounded_fact(facts, copylint,
                                               english_only=english_only)
    except Exception as exc:                    # noqa: BLE001 - classified
        fact, reason = None, "%s: %s" % (type(exc).__name__, exc)
    if fact:
        out["quote"] = fact["quote"]
        out["anchor_grounded"] = len(str(fact["quote"]).split())
    else:
        out["hold"] = out["hold"] or reason
    return out


# ----------------------------------------------------------------- batches

def summarise(per_domain):
    """The five numbers, plus the ones that keep them honest."""
    n = len(per_domain)
    fact = [m for m in per_domain if m["facts"]]
    passes = [m for m in fact if m["rule1"]]
    single = [m for m in passes if len(m["matched"]) == 1]
    category = [m for m in passes
                if m["matched"] and all(w in lanek.CATEGORY_WORDS
                                        for w in m["matched"])]
    grounded = [m for m in fact if m["anchor_grounded"]]
    t_anchors = sorted(m["anchor_template"] for m in passes) or [0]
    g_anchors = sorted(m["anchor_grounded"] for m in grounded) or [0]
    facts_total = sum(m["facts"] for m in per_domain)
    nav_total = sum(m["nav_facts"] for m in per_domain)
    nav_word_total = sum(m["nav_words"] for m in per_domain)
    chars_total = sum(m["snippet_chars"] for m in per_domain)
    return {
        "domains": n,
        "contacts": sum(m["contacts"] for m in per_domain),
        "with_usable_fact": len(fact),
        "contacts_with_usable_fact": sum(m["contacts"] for m in fact),
        "rule1": len(passes),
        "contacts_rule1": sum(m["contacts"] for m in passes),
        "single_word": len(single),
        "single_word_top": collections.Counter(
            m["matched"][0] for m in single).most_common(8),
        "category_only": len(category),
        "facts_total": facts_total,
        "facts_navigation_led_boolean": nav_total,
        "facts_navigation_led_boolean_pct":
            round(100.0 * nav_total / (facts_total or 1), 1),
        # THE COMPARABLE ONE. See `nav_words`.
        "menu_words_per_400_chars":
            round(400.0 * nav_word_total / (chars_total or 1), 2),
        "snippet_chars_total": chars_total,
        # THE OPERATOR'S STATISTIC, both readings.
        "anchor_template_median": statistics.median(t_anchors),
        "anchor_template_ge4": sum(1 for a in t_anchors if a >= 4),
        "quotable_span_found": len(grounded),
        "quotable_span_pct_of_fact_domains":
            round(100.0 * len(grounded) / (len(fact) or 1), 1),
        "anchor_grounded_median": statistics.median(g_anchors),
        "anchor_grounded_ge7": sum(1 for a in g_anchors if a >= 7),
        "holds": collections.Counter(
            m["hold"] for m in per_domain if m["hold"]).most_common(6),
    }


def line(label, s, width=34):
    n = s["domains"] or 1
    fac = s["with_usable_fact"] or 1
    return ("%-*s %6d %6d %5.1f%% %6d %5.1f%% %6d %5.1f%% %6.1f %6d %5.1f%% "
            "%6.1f" % (width, label[:width], s["domains"],
                       s["with_usable_fact"],
                       100.0 * s["with_usable_fact"] / n,
                       s["rule1"], 100.0 * s["rule1"] / n,
                       s["single_word"],
                       100.0 * s["single_word"] / (s["rule1"] or 1),
                       s["anchor_template_median"],
                       s["quotable_span_found"],
                       100.0 * s["quotable_span_found"] / fac,
                       s["anchor_grounded_median"]))


HEADER = ("%-34s %6s %6s %6s %6s %6s %6s %6s %6s %6s %6s %6s"
          % ("", "doms", "fact", "", "rule1", "", "1word", "", "anchT",
             "quote", "", "anchG"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", required=True, help="the crawl log jsonl")
    ap.add_argument("--cohort", help="lane J's cohort, for the batch ORDER: "
                                     "batches follow shippability, not the "
                                     "order threads happened to finish in")
    ap.add_argument("--cap", type=int, action="append", default=[],
                    help="re-truncate snippets to this many chars before "
                         "measuring; repeat to compare (e.g. --cap 400 "
                         "--cap 2000)")
    ap.add_argument("--batch", type=int, default=2000)
    ap.add_argument("--client", default="productive")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", default="")
    ap.add_argument("--cohort-out", default="",
                    help="JSONL of the domains a push could carry, in the "
                         "order it should carry them, with the anchor on "
                         "each row. Written from the LAST --cap given.")
    args = ap.parse_args(argv)

    caps = args.cap or [0]
    lh, sha = lane_h(HERE)
    print("lane H render blob %s (loaded, not forked)" % sha)
    config = clients.load(args.client)
    rows = read_log(args.log)

    order = list(rows)
    if args.cohort:
        ranked = crawl.prioritise_cohort(crawl.read_cohort(args.cohort))
        seen, order = set(), []
        for rec in ranked:
            if rec["domain"] in rows and rec["domain"] not in seen:
                seen.add(rec["domain"])
                order.append(rec["domain"])
        order += [d for d in rows if d not in seen]
    if args.limit:
        order = order[:args.limit]
    print("%d domain(s) in the log, measuring %d" % (len(rows), len(order)))

    report = {"log": os.path.basename(args.log), "measured": len(order),
              "caps": {}}
    for cap in caps:
        per = [measure_domain(capped(rows[d], cap), config, lh)
               for d in order]
        batches = []
        print("")
        print("CAP %s   (anchT = median anchor of the TEMPLATE opener; "
              "anchG = median anchor a pack-grounded render would carry)"
              % (cap or "as stored"))
        print(HEADER)
        for start in range(0, len(per), args.batch):
            chunk = per[start:start + args.batch]
            s = summarise(chunk)
            s["batch"] = "%d-%d" % (start + 1, start + len(chunk))
            batches.append(s)
            print(line("batch %s" % s["batch"], s))
        total = summarise(per)
        print(line("ALL", total))
        print("  facts %d, %s chars of snippet, MENU WORDS PER 400 CHARS "
              "%.2f (lane K's comparable density; the boolean 'navigation-"
              "led' fires on %d of them and is not comparable across caps)"
              % (total["facts_total"], total["snippet_chars_total"],
                 total["menu_words_per_400_chars"],
                 total["facts_navigation_led_boolean"]))
        print("  quotable span on %d of %d fact-carrying domains (%.1f%%)"
              % (total["quotable_span_found"], total["with_usable_fact"],
                 total["quotable_span_pct_of_fact_domains"]))
        print("  contacts: %d attempted, %d with a usable fact, %d passing "
              "rule 1" % (total["contacts"],
                          total["contacts_with_usable_fact"],
                          total["contacts_rule1"]))
        print("  single words: %s" % total["single_word_top"])
        print("  holds: %s" % total["holds"])
        report["caps"][str(cap)] = {"total": total, "batches": batches,
                                    "per_domain": [
                                        {"domain": m["domain"],
                                         "contacts": m["contacts"],
                                         "facts": m["facts"],
                                         "rule1": m["rule1"],
                                         "matched": m["matched"],
                                         "anchor_template":
                                             m["anchor_template"],
                                         "anchor_grounded":
                                             m["anchor_grounded"]}
                                        for m in per]}

    if len(caps) == 2:
        lo, hi = [report["caps"][str(c)]["per_domain"] for c in caps]
        by_lo = {m["domain"]: m for m in lo}
        gained_rule1 = gained_quote = gained_anchor = lost = 0
        lost_rule1 = 0
        off_single = 0
        for m in hi:
            b = by_lo.get(m["domain"]) or {}
            if m["rule1"] and not b.get("rule1"):
                gained_rule1 += 1
            if b.get("rule1") and not m["rule1"]:
                lost_rule1 += 1
            if m["anchor_grounded"] and not b.get("anchor_grounded"):
                gained_quote += 1
            if m["anchor_grounded"] > (b.get("anchor_grounded") or 0):
                gained_anchor += 1
            if m["anchor_grounded"] < (b.get("anchor_grounded") or 0):
                lost += 1
            if (b.get("rule1") and len(b.get("matched") or []) == 1
                    and m["rule1"] and len(m["matched"]) > 1):
                off_single += 1
        report["improvement"] = {
            "from_cap": caps[0], "to_cap": caps[1],
            "domains_gaining_rule1": gained_rule1,
            "domains_losing_rule1": lost_rule1,
            "domains_gaining_a_quotable_span": gained_quote,
            "domains_with_a_longer_quotable_span": gained_anchor,
            "domains_with_a_shorter_quotable_span": lost,
            "domains_off_a_single_word": off_single,
        }
        print("")
        print("WHAT THE CAP BOUGHT, %s -> %s, on the SAME crawl:"
              % (caps[0], caps[1]))
        for key, value in report["improvement"].items():
            if key.startswith("from") or key.startswith("to"):
                continue
            print("  %-42s %6d" % (key.replace("_", " "), value))

    if args.cohort_out:
        # THE ORDER IS ALREADY RIGHT. `order` is lane J's shippability
        # ranking when `--cohort` was given, so this writes it out with the
        # measurement attached rather than re-sorting on a different key and
        # handing the push a third opinion about what to send first.
        #
        # `anchor_grounded` travels with each row because it is the number
        # that decides whether a domain is worth rendering from its pack:
        # 0 means there is nothing on that site worth quoting and rule 1
        # would pass on a category word. NOT a permission to send.
        last = report["caps"][str(caps[-1])]["per_domain"]
        by_domain = {m["domain"]: m for m in last}
        rank = 0
        written = 0
        with open(args.cohort_out, "w", encoding="utf-8") as handle:
            for domain in order:
                m = by_domain.get(domain)
                if not m or not m["rule1"]:
                    continue
                rank += 1
                row = rows[domain]
                handle.write(json.dumps({
                    "rank": rank,
                    "domain": domain,
                    "contacts": m["contacts"],
                    "mx_status": row.get("mx_status"),
                    "estate_holds_an_excluded_person":
                        row.get("estate_holds_an_excluded_person"),
                    "facts": m["facts"],
                    "retrieved_at": row.get("retrieved_at"),
                    "rule1_matched_words": m["matched"],
                    "rests_on_one_word": len(m["matched"]) == 1,
                    "anchor_template": m["anchor_template"],
                    "anchor_grounded": m["anchor_grounded"],
                    "snippet_cap": caps[-1] or "as stored",
                }, ensure_ascii=False) + "\n")
                written += 1
        print("")
        print("cohort written to %s: %d domain(s) passing rule 1 at cap %s, "
              "in lane J's shippability order, each carrying its anchor"
              % (args.cohort_out, written, caps[-1] or "as stored"))

    if args.json:
        slim = dict(report)
        slim["caps"] = {k: {"total": v["total"], "batches": v["batches"]}
                        for k, v in report["caps"].items()}
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(slim, handle, indent=1, default=str)
        print("written to %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
