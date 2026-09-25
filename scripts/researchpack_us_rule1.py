"""Four numbers about the US pack crawl, and they are four different questions.

LANE K, 2026-09-25. Reads the crawl log written by
`scripts/researchpack_us_crawl.py` and answers, with the denominator every
time:

    attempted            domains put to the crawler
    crawled              domains that produced a classified outcome
    with a usable fact   domains where `facts.make` accepted at least one page
                         AND `site.on_this_domain` had already admitted it
    passing rule 1       domains whose pack would carry a step-1 opener

Lane C found the gap between the second and the third is where the truth
lives. On this cohort there is a fourth gap and it is larger.

## RULE 1 CANNOT BE ASKED OF THIS COHORT THE WAY IT WAS ASKED OF THE UK/EU

The UK/EU cohort had rendered copy: `work/stage/s7-copy.jsonl` carried an
opener per lead and `copylint` could be run against it. **Of the 16,247 US
supply domains, 21 have a rendered s7 row and 16,226 do not.** There is no
opener to lint, so a rule-1 number for this cohort is necessarily a
PROJECTION and is labelled one everywhere below.

The projection is not invented. `src/cadence.py` renders step 1 from
`TEMPLATES["persona_pain"]` and `template_vars`, and when a record carries no
`evidence` - which is every record in this system, because `evidence` is
written only by `generate.persona_angle`, which needs a model and none ships
- the opener is fully determined by three things on the supply row and in
the client config:

    "{first_name}, I work with {sector} teams on {angle_phrase}, and I do
     not know how {company} handles it"

So this module CALLS `cadence.template_vars`, `cadence.render` and
`copylint.first_line`/`pack_text`/`_WORD` rather than restating any of them.
A second copy of the matching would be a report that agrees with itself and
not with the gate.

## THE GREETING TOKEN IS A RULE-1 PASS ALL BY ITSELF

`copylint` rule 1 keeps opener tokens of MORE THAN FOUR characters.
`template_vars` falls back to `first_name = "there"` when no contact name is
known, and "there" is five characters. Any site whose prose contains the
word "there" therefore passes rule 1 on the greeting alone, with nothing
about the company involved.

That is reported separately and is NEVER counted as grounding: the headline
projection drops the greeting token. Both numbers are printed, because the
difference is the size of the hole.

## THE SINGLE-WORD STATISTIC

Lane C measured that 54 of 117 UK/EU rule-1 passes rested on exactly one
distinct word and that the word was `marketing` in 53 of them - because S7
rendered copy before any pack existed, so the openers shared vocabulary with
the research rather than referencing it. The same statistic is computed here
and it is the number that decides whether this crawl bought anything.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from src import cadence, clients, copylint                  # noqa: E402

#: Category words. A pass that rests on nothing but these is a pass on the
#: fact that both texts are about the same industry. Lane C's hand-list,
#: extended with the words this cohort's sectors and angles contribute.
CATEGORY_WORDS = {
    "marketing", "advertising", "agence", "design", "digital", "teams",
    "services", "software", "development", "creative", "studio", "agency",
    "brand", "branding", "media", "content", "strategy", "consulting",
    "technology", "solutions", "products", "product", "business", "clients",
    "customers", "there", "handles", "company", "group", "partners",
    "global", "people", "project", "projects", "utilisation", "utilization",
    "capacity", "margin", "budget", "resourcing", "finance", "billing",
    "profitability", "visible", "monday", "reconciliation", "entity",
    "planning", "scope", "creep", "visibility", "system", "labs", "works",
}


#: THE SNIPPET IS THE FIRST 400 CHARACTERS OF THE PAGE, AND ON A MODERN SITE
#: THAT IS THE NAVIGATION BAR. `webfetch.readable_text` returns the document
#: in reading order and `facts.SNIPPET_CHARS` cuts at 400, so a site whose
#: header carries a menu, a language switcher and a cookie line spends its
#: whole snippet on them before the prose begins. `copylint.pack_text` then
#: matches rule 1 against that, which is how `software`, `development` and
#: `teams` come to be the words doing the work.
#:
#: Measured rather than asserted: a snippet carrying three or more of these
#: is counted as navigation-led. The list is menu furniture only - no word
#: here is something a company says ABOUT ITSELF.
NAV_WORDS = ("home", "about", "about us", "contact", "contact us", "menu",
             "careers", "blog", "news", "pricing", "login", "log in",
             "sign in", "sign up", "privacy", "terms", "cookie", "search",
             "resources", "support", "faq", "newsletter", "subscribe",
             "book a demo", "get started", "request a demo", "our work",
             "case studies", "portfolio", "services", "products",
             "skip to content", "toggle", "english", "language")


def navigation_led(snippet):
    low = " %s " % str(snippet or "").lower()
    return sum(1 for w in NAV_WORDS if " %s " % w in low) >= 3


def read_log(path):
    rows = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            rows[row.get("domain")] = row      # last write wins on a resume
    return rows


def pack_of(row):
    return {"facts": row.get("facts") or []}


def openers_for(row, config):
    """Every step-1 opener this domain could carry, one per persona/angle.

    Built by production's own renderer. `first_name` is left at
    `template_vars`' own no-contact fallback, and the greeting token is
    stripped by the caller rather than here, so the two readings come off
    the same rendered string.
    """
    name = str(row.get("name") or "").strip()
    industry = str(row.get("industry") or "").strip()
    rec = {"id": row.get("domain"), "domain": row.get("domain"),
           "company": name,
           "company_facts": {"name": name, "industry": industry},
           "evidence": {}}
    out = []
    for persona in ("champion", "economic_buyer"):
        for angle in clients.angles_for(config, persona):
            contact = {"name": None, "persona": persona, "angle": angle,
                       "email": "x@%s" % row.get("domain")}
            try:
                values = cadence.template_vars(rec, contact, config)
                body = cadence.render(cadence.TEMPLATES["persona_pain"],
                                      values)["body"]
            except Exception:                  # noqa: BLE001 - classified
                # CompanyNameUnusable is the real one: the supply row's name
                # is domain-shaped and production would refuse to render.
                continue
            out.append((persona, angle, copylint.first_line(body)))
    return out


def rule1_tokens(opener, drop_greeting=True):
    """Exactly `copylint`'s own tokens, optionally without the greeting.

    `copylint` takes `[t for t in _WORD.findall(opener.lower()) if len(t) > 4]`.
    The greeting is the text before the first comma and it is not a claim
    about the company, so the honest reading drops it.
    """
    text = opener
    if drop_greeting and "," in opener:
        text = opener.split(",", 1)[1]
    return [t for t in copylint._WORD.findall(text.lower()) if len(t) > 4]


def matched(tokens, supported):
    return sorted({t for t in tokens if t in supported})


def analyse(rows, config, s7_openers=None):
    s7_openers = s7_openers or {}
    total = len(rows)
    outcomes = collections.Counter()
    crawled = fact = unsafe = 0
    pass_any = pass_all = pass_greeting_only = 0
    no_opener = 0
    single_word = collections.Counter()
    all_words = collections.Counter()
    single_word_passes = single_word_best_case = 0
    category_only = category_only_best_case = 0
    facts_total = facts_no_source = facts_no_snippet = 0
    facts_no_published_at = facts_nav = nav_only_domains = 0
    passing = []

    for domain, row in rows.items():
        outcomes[row.get("outcome")] += 1
        if row.get("outcome") == "UNSAFE_URL":
            unsafe += 1
            continue
        crawled += 1
        facts = row.get("facts") or []
        if not facts:
            continue
        fact += 1
        for one in facts:
            facts_total += 1
            if not one.get("source_url"):
                facts_no_source += 1
            if not one.get("snippet"):
                facts_no_snippet += 1
            if not one.get("published_at"):
                facts_no_published_at += 1
            if navigation_led(one.get("snippet")):
                facts_nav += 1
        if all(navigation_led(one.get("snippet")) for one in facts):
            nav_only_domains += 1

        supported = copylint.pack_text(pack_of(row))
        openers = openers_for(row, config)
        if not openers:
            no_opener += 1
            continue

        hits, greeting_hits = [], []
        for _persona, _angle, opener in openers:
            hits.append(matched(rule1_tokens(opener, True), supported))
            greeting_hits.append(matched(rule1_tokens(opener, False), supported))

        passed = [h for h in hits if h]
        if passed:
            pass_any += 1
            passing.append({
                "domain": domain,
                "mx_status": row.get("mx_status"),
                "slice": row.get("slice"),
                "facts": len(facts),
                "thinnest_grounding": min(passed, key=len),
                "richest_grounding": max(passed, key=len),
                "angles_passing": len(passed),
                "angles_tried": len(hits),
            })
            # WHICH ANGLE A DOMAIN GETS IS NOT KNOWN TODAY - it follows from
            # a contact's title and no contacts are sourced yet. So the
            # single-word statistic is BRACKETED rather than asserted: the
            # thinnest angle is the worst this domain could be grounded on
            # and the richest is the best. Both are reported.
            thinnest = min(passed, key=len)
            richest = max(passed, key=len)
            all_words.update(thinnest)
            if len(thinnest) == 1:
                single_word_passes += 1
                single_word[thinnest[0]] += 1
            if len(richest) == 1:
                single_word_best_case += 1
            if all(w in CATEGORY_WORDS for w in thinnest):
                category_only += 1
            if all(w in CATEGORY_WORDS for w in richest):
                category_only_best_case += 1
        if all(h for h in hits):
            pass_all += 1
        if not passed and any(g for g in greeting_hits):
            pass_greeting_only += 1

    return {
        "attempted": total,
        "unsafe_url": unsafe,
        "crawled": crawled,
        "with_usable_fact": fact,
        "no_renderable_opener": no_opener,
        "rule1_projected_any_angle": pass_any,
        "rule1_projected_every_angle": pass_all,
        "rule1_on_the_greeting_alone": pass_greeting_only,
        "single_word_passes": single_word_passes,
        "single_word_passes_best_case": single_word_best_case,
        "category_words_only": category_only,
        "category_words_only_best_case": category_only_best_case,
        "single_word_top": single_word.most_common(12),
        "words_top": all_words.most_common(20),
        "outcomes": outcomes.most_common(),
        "facts_total": facts_total,
        "facts_without_source_url": facts_no_source,
        "facts_without_snippet": facts_no_snippet,
        "facts_without_published_at": facts_no_published_at,
        "facts_navigation_led": facts_nav,
        "domains_whose_every_fact_is_navigation": nav_only_domains,
        "s7_measured": measure_s7(rows, s7_openers),
        "passing": passing,
    }


def measure_s7(rows, s7_openers):
    """Rule 1 as `copylint` itself computes it, on the leads that HAVE copy.

    No projection here: these are rendered openers out of
    `work/stage/s7-copy.jsonl`. It is a small number and it is the only
    part of this report that is a measurement rather than a projection.
    """
    leads, packs = [], {}
    for email, body in s7_openers.items():
        domain = email.split("@")[-1].lower()
        row = rows.get(domain)
        if not row:
            continue
        leads.append({"id": email, "steps": [{"body": body}]})
        packs[email] = pack_of(row)
    if not leads:
        return {"leads": 0}
    report = copylint.check_batch(leads, packs, steps_expected=1)
    offenders = set(report["offenders"]["step1_without_pack_fact"])
    detail = collections.Counter()
    singles = 0
    for lead in leads:
        if lead["id"] in offenders:
            continue
        supported = copylint.pack_text(packs[lead["id"]])
        opener = copylint.first_line(lead["steps"][0]["body"])
        words = matched([t for t in copylint._WORD.findall(opener.lower())
                         if len(t) > 4], supported)
        if len(words) == 1:
            singles += 1
            detail[words[0]] += 1
    return {"leads": len(leads),
            "pass_rule1": len(leads) - len(offenders),
            "single_word_passes": singles,
            "single_word_top": detail.most_common(8)}


def load_s7(path):
    out = {}
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("state") != "rendered":
                continue
            body = (row.get("variables") or {}).get("body_1")
            if row.get("email") and body:
                out[row["email"]] = body
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", required=True)
    ap.add_argument("--client", default="productive")
    ap.add_argument("--s7", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--cohort-out", default="",
                    help="JSONL of the domains a push could carry today: "
                         "known_allowed first, then the largest slices")
    args = ap.parse_args(argv)

    rows = read_log(args.log)
    config = clients.load(args.client)
    report = analyse(rows, config, load_s7(args.s7))

    n = report["attempted"] or 1
    print("attempted                     %6d" % report["attempted"])
    print("  refused by check_url        %6d" % report["unsafe_url"])
    print("crawled                       %6d  %5.1f%%"
          % (report["crawled"], 100.0 * report["crawled"] / n))
    print("with at least one usable fact %6d  %5.1f%%"
          % (report["with_usable_fact"], 100.0 * report["with_usable_fact"] / n))
    print("  no renderable opener        %6d" % report["no_renderable_opener"])
    print("PROJECTED rule 1, any angle   %6d  %5.1f%%"
          % (report["rule1_projected_any_angle"],
             100.0 * report["rule1_projected_any_angle"] / n))
    print("PROJECTED rule 1, every angle %6d  %5.1f%%"
          % (report["rule1_projected_every_angle"],
             100.0 * report["rule1_projected_every_angle"] / n))
    print("  would pass on the GREETING  %6d   (never counted above)"
          % report["rule1_on_the_greeting_alone"])
    passes = report["rule1_projected_any_angle"] or 1
    print("of those passes, bracketed over the angle the contact decides:")
    print("  rest on ONE distinct word   %6d  %5.1f%%  (thinnest angle)"
          % (report["single_word_passes"],
             100.0 * report["single_word_passes"] / passes))
    print("                              %6d  %5.1f%%  (richest angle)"
          % (report["single_word_passes_best_case"],
             100.0 * report["single_word_passes_best_case"] / passes))
    print("  rest on CATEGORY words only %6d  %5.1f%%  (thinnest angle)"
          % (report["category_words_only"],
             100.0 * report["category_words_only"] / passes))
    print("                              %6d  %5.1f%%  (richest angle)"
          % (report["category_words_only_best_case"],
             100.0 * report["category_words_only_best_case"] / passes))
    print("  the single words:           %s" % report["single_word_top"])
    print("  commonest matching words:   %s" % report["words_top"][:10])
    facts_n = report["facts_total"] or 1
    print("facts written                 %6d" % report["facts_total"])
    print("  with no source url          %6d" % report["facts_without_source_url"])
    print("  with no snippet             %6d" % report["facts_without_snippet"])
    print("  with no published_at        %6d  %5.1f%%  (see the doc: a crawled"
          " page carries no date worth trusting; retrieved_at is pack-level)"
          % (report["facts_without_published_at"],
             100.0 * report["facts_without_published_at"] / facts_n))
    print("  NAVIGATION-LED snippet      %6d  %5.1f%%"
          % (report["facts_navigation_led"],
             100.0 * report["facts_navigation_led"] / facts_n))
    print("  domains where EVERY fact is navigation  %6d"
          % report["domains_whose_every_fact_is_navigation"])
    print("crawler outcomes:             %s" % report["outcomes"])
    print("MEASURED on the leads that have rendered copy: %s"
          % json.dumps(report["s7_measured"]))

    if args.cohort_out:
        # The order the brief asked for: only ~2,500 addresses can be
        # verified today, so known_allowed outranks unknown_provider and
        # the largest slices come first. Nothing here is a permission to
        # send; it is the join key the push needs.
        sizes = collections.Counter(r["slice"] for r in report["passing"])
        ranked = sorted(report["passing"],
                        key=lambda r: ({"known_allowed": 0,
                                        "unknown_provider": 1}.get(
                                           r["mx_status"], 9),
                                       -sizes[r["slice"]],
                                       str(r["slice"]), r["domain"]))
        with open(args.cohort_out, "w", encoding="utf-8") as handle:
            for i, row in enumerate(ranked, 1):
                row = dict(row, rank=i)
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("cohort written to %s (%d domain(s), ranked)"
              % (args.cohort_out, len(ranked)))

    if args.json:
        report = dict(report)
        report.pop("passing", None)      # the list is the cohort file's job
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, default=str)
        print("written to %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
