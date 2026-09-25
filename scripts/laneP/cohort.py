#!/usr/bin/env python3
"""LANE P: build LinkedIn-ONLY cohorts, provider-checked, match-validated.

WHAT THIS IS AND IS NOT
-----------------------
It is a READ-ONLY cohort builder. It writes nothing to any provider: every
HeyReach write verb is replaced by a refusal before the first call, and every
EmailBison call goes through a GET-only wrapper. The foreground session
performs the enrollment.

THE FOUR GATES, in the order they are cheapest to answer
--------------------------------------------------------
  E1  EmailBison, by address. `?search=<address>` filtered to an EXACT
      address match, then `lead_campaign_data` - the provider's own per-lead
      array of the campaigns it is in. Non-empty is a REJECT.
      Absent lead is a pass: a lead that does not exist is in no campaign.
  E2  EmailBison, by name. The alias route: the same person under an address
      we do not hold. Rows are matched on normalised first+last AND company,
      never on the search engine's own idea of relevance - a bare `?search=`
      is token-ish and matched eleven strangers on one probe.
  H1  HeyReach, by profile url. `GetCampaignsForLead` - EVERY campaign the
      person is in, the client's included. Non-empty is a REJECT. This is the
      gate the store cannot answer: one of the first three candidates probed
      was in THIRTEEN LinkedIn campaigns while our store recorded none.
  M1  Match validation. `/lead/GetLead` returns the provider's own firstName,
      lastName and companyName for the profile url. Three verdicts:
        admitted      surname AND company agree
        refused       either disagrees
        unverifiable  the provider will not say - NOT A PASS, excluded
      Fail-closed by construction: the verdict starts `unverifiable` and only
      evidence moves it.

A candidate passes only if E1, E2 and H1 all clear AND M1 is `admitted`.

THE FIFTH AXIS
--------------
geo / vertical / headcount band / signal state / persona. `work/signals.jsonl`
is EMPTY (0 bytes, measured), so the signal state of every candidate in the
store is COLD - there is no first-party signal on anybody. The axis is
therefore homogeneous by measurement rather than by selection, and the tag
records that rather than implying a signal nobody has.
"""
import argparse
import collections
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot  # noqa: E402

from src.providers import bison, heyreach, ProviderError  # noqa: E402
from src import linkedin as li, geo, segments, personas  # noqa: E402

try:
    from src import clients
    CONFIG = clients.load("productive")
except Exception:  # noqa: BLE001
    CONFIG = None


def refuse_write(*a, **kw):
    raise SystemExit("LANE P is reads-only: refusing a HeyReach write")


heyreach._write_body = refuse_write
heyreach._write = refuse_write
_bison_request = bison.request


def bison_get(url):
    if boot.CALLS["by"].get("bison", 0) >= HARD_CAP:
        raise SystemExit("LANE P request cap reached")
    boot.CALLS["n"] += 1
    boot.CALLS["by"]["bison"] = boot.CALLS["by"].get("bison", 0) + 1
    return _bison_request("GET", url, bison.headers())


def hr_count(n=1):
    boot.CALLS["n"] += n
    boot.CALLS["by"]["heyreach"] = boot.CALLS["by"].get("heyreach", 0) + n


HARD_CAP = 4000
QUEUE = os.path.join(boot.PROD, "work", "queue.jsonl")

# ------------------------------------------------------------------ tags

# SHORT CODES, BECAUSE THE NAME IS THE RECOVERY KEY AND IT HAS 50 CHARACTERS.
# HeyReach documents no campaign delete and no list delete, so a name is the
# only handle a campaign created-but-unrecorded can ever be found by. The
# first build of this lane spelled the verticals out and two names came back
# truncated at exactly 50 - `...-CHAMPION-COLD-S116989-` - which silently
# drops the day suffix and is how two days' campaigns collide on one name.
# `cohort_name` now REFUSES an over-long name rather than trimming it.
VERTICAL_CODE = {
    "Digital Marketing Agency": "DIGI",
    "Performance Marketing Agency": "PERF",
    "Creative / Branding Agency": "CREA",
    "SEO Agency": "SEO",
    "PR / Communications Agency": "PR",
    "Software Development Agency": "SOFT",
    "Product Development Agency": "PROD",
    "Design / UX Agency": "DSGN",
    "Consulting": "CONS",
    "Professional Services": "PSRV",
}
REGION_CODE = {
    "UK": "UK", "DACH": "DACH", "Nordics": "NORDICS", "Benelux": "BENELUX",
    "CEE": "CEE", "Southern Europe": "SEUROPE", "US East": "USEAST",
    "US Central": "USCENTRAL", "US West": "USWEST", "Canada": "CANADA",
    "Australia / New Zealand": "ANZ",
}
PERSONA_CODE = {"economic_buyer": "BUY", "champion": "CHM"}
SIGNAL_COLD = "COLD"
SIGNAL_CODE = {SIGNAL_COLD: "CLD"}


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def company_tokens(name):
    stop = {"ltd", "limited", "inc", "llc", "llp", "gmbh", "bv", "ab", "as",
            "plc", "co", "company", "group", "agency", "studio", "the",
            "and", "of", "digital", "media", "marketing", "creative"}
    return {t for t in norm(name).split() if len(t) > 2 and t not in stop}


# ------------------------------------------------------------- selection

def survivors():
    """Contacts the STORE cannot rule out. The provider rules on them next."""
    out = []
    with open(QUEUE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("do_not_contact") or rec.get("hold_reason"):
                continue
            if str(rec.get("state")) in ("dropped", "held", "do_not_contact"):
                continue
            for c in (rec.get("contacts") or []):
                if not isinstance(c, dict):
                    continue
                url = li.canonical(c.get("linkedin"))
                if not url:
                    continue
                if (c.get("do_not_contact") or c.get("stopped")
                        or c.get("paused")):
                    continue
                if c.get("campaign_id_linkedin") or c.get("bison_lead_id"):
                    continue
                seg = {}
                g = {}
                try:
                    seg = segments.classify(rec, CONFIG) or {}
                except Exception:  # noqa: BLE001
                    pass
                try:
                    g = geo.from_record(rec, CONFIG) or {}
                except Exception:  # noqa: BLE001
                    pass
                persona = c.get("persona")
                if not persona:
                    try:
                        persona, _score = personas.classify(c, CONFIG)
                    except Exception:  # noqa: BLE001
                        persona = None
                region = g.get("region") or seg.get("region")
                out.append({
                    "record_id": rec.get("id"),
                    "contact_key": c.get("key"),
                    "name": c.get("name"),
                    "title": c.get("title"),
                    "company": rec.get("company")
                              or (rec.get("company_facts") or {}).get("name"),
                    "domain": rec.get("domain"),
                    "email": c.get("email"),
                    "profile_url": url,
                    "region": region,
                    "vertical": seg.get("vertical"),
                    "band": seg.get("employee_band"),
                    "persona": persona,
                    "signal_state": SIGNAL_COLD,
                    "timezone": g.get("timezone") or seg.get("timezone"),
                    "timezone_confidence": g.get("timezone_confidence"),
                })
    return out


def cell_of(row):
    return (row["region"], row["vertical"], row["band"], row["persona"],
            row["signal_state"])


def complete(row):
    """Every axis answered. An 'Other'/'UNKNOWN' axis is not a tag."""
    return all(row.get(k) not in (None, "", "UNKNOWN", "Other")
               for k in ("region", "vertical", "band", "persona"))


class NameTooLong(ValueError):
    """The provider's 50-character ceiling, refused rather than trimmed."""


def cohort_name(cell, seat_ref, day="D1"):
    """<=50 chars, unique per seat and day, carrying all five tags.

    RAISES rather than truncating. A trimmed name loses its day suffix first,
    which is exactly the character that keeps tomorrow's campaign for the same
    cohort and seat from colliding with today's - and on this provider a
    colliding name is unrecoverable, because there is no delete.
    """
    region, vertical, band, persona, signal = cell
    name = "-".join(["RP", REGION_CODE.get(region, "OTHER"),
                     VERTICAL_CODE.get(vertical, "AGCY"), str(band),
                     PERSONA_CODE.get(persona, "OTH"),
                     SIGNAL_CODE.get(signal, str(signal)[:4]),
                     f"S{seat_ref}", day])
    if len(name) > 50:
        raise NameTooLong(
            f"{name!r} is {len(name)} characters and the provider takes 50. "
            f"Shorten a code in cohort.py; do NOT trim the name")
    return name


# ----------------------------------------------------------------- gates

def gate_e1(row):
    """In an EmailBison campaign, by address?"""
    address = str(row.get("email") or "").strip().lower()
    if not address:
        return {"verdict": "no_address", "campaigns": []}
    import urllib.parse
    status, data = bison_get(
        f"{bison.base()}/leads?search={urllib.parse.quote(address)}")
    if not (status and 200 <= status < 300) or not isinstance(data, dict):
        return {"verdict": "unverifiable", "status": status}
    rows = data.get("data")
    if not isinstance(rows, list):
        return {"verdict": "unverifiable", "status": status}
    exact = [r for r in rows if isinstance(r, dict)
             and str(r.get("email") or "").strip().lower() == address]
    if not exact:
        return {"verdict": "no_lead", "campaigns": []}
    camps = sorted({e.get("campaign_id") for e in
                    (exact[0].get("lead_campaign_data") or [])
                    if isinstance(e, dict)})
    return {"verdict": "in_campaigns" if camps else "lead_but_no_campaign",
            "campaigns": camps,
            "lead_id": exact[0].get("id")}


def gate_e2(row):
    """The same person under an address we do not hold."""
    name = norm(row.get("name"))
    if not name:
        return {"verdict": "unverifiable", "why": "no name to ask with"}
    import urllib.parse
    status, data = bison_get(
        f"{bison.base()}/leads?search={urllib.parse.quote(row['name'])}")
    if not (status and 200 <= status < 300) or not isinstance(data, dict):
        return {"verdict": "unverifiable", "status": status}
    rows = data.get("data")
    if not isinstance(rows, list):
        return {"verdict": "unverifiable", "status": status}
    mine = company_tokens(row.get("company"))
    hits = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        full = norm(f"{r.get('first_name') or ''} {r.get('last_name') or ''}")
        if full != name:
            continue
        camps = sorted({e.get("campaign_id") for e in
                        (r.get("lead_campaign_data") or [])
                        if isinstance(e, dict)})
        theirs = company_tokens(r.get("company"))
        same_company = bool(mine & theirs) if (mine and theirs) else None
        hits.append({"campaigns": camps, "same_company": same_company})
    aliased = [h for h in hits if h["campaigns"] and h["same_company"]]
    ambiguous = [h for h in hits if h["campaigns"] and h["same_company"] is None]
    if aliased:
        return {"verdict": "alias_in_campaigns",
                "campaigns": sorted({c for h in aliased
                                     for c in h["campaigns"]})}
    if ambiguous:
        return {"verdict": "unverifiable", "why": "name matched, company "
                                                  "unknown on both sides"}
    return {"verdict": "clear", "name_hits": len(hits)}


def gate_h1(row):
    """Already in ANY LinkedIn campaign - ours or the client's?"""
    try:
        camps, total = heyreach.campaigns_for_lead(
            profile_url=row["profile_url"])
        hr_count()
    except Exception as exc:  # noqa: BLE001
        hr_count()
        return {"verdict": "unverifiable",
                "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
    if total:
        return {"verdict": "in_linkedin_campaigns", "n": total,
                "statuses": sorted({str(c.get("campaignStatus"))
                                    for c in camps}),
                "lead_statuses": sorted({str(c.get("leadStatus"))
                                         for c in camps})}
    return {"verdict": "clear", "n": 0}


def gate_m1(row):
    """Does this profile belong to the person AND company we think?"""
    try:
        prof = heyreach.lead_profile(row["profile_url"])
        hr_count()
    except Exception as exc:  # noqa: BLE001
        hr_count()
        return {"verdict": "unverifiable",
                "why": f"{type(exc).__name__}: {str(exc)[:80]}"}
    first = norm(prof.get("firstName"))
    last = norm(prof.get("lastName"))
    company = prof.get("companyName")
    if not (last and company):
        return {"verdict": "unverifiable",
                "why": "provider gave no surname or no company"}
    ours = norm(row.get("name")).split()
    if not ours:
        return {"verdict": "unverifiable", "why": "no stored name"}
    surname_ok = last in ours
    first_ok = (first in ours) if first else False
    mine = company_tokens(row.get("company"))
    theirs = company_tokens(company)
    company_ok = bool(mine & theirs)
    if not mine or not theirs:
        return {"verdict": "unverifiable", "why": "company unnameable on one "
                                                  "side"}
    if surname_ok and company_ok:
        return {"verdict": "admitted", "first_name_agreed": first_ok,
                "position": prof.get("position") is not None}
    return {"verdict": "refused",
            "surname_agreed": surname_ok, "company_agreed": company_ok}


def verify(row, pause=0.15):
    """The gauntlet, cheapest first, and it stops at the first REJECT."""
    result = {"gates": {}}
    e1 = gate_e1(row)
    result["gates"]["E1"] = e1
    if e1["verdict"] == "in_campaigns":
        result["verdict"] = "rejected:in_email_campaign"
        return result
    if e1["verdict"] == "unverifiable":
        result["verdict"] = "excluded:E1_unverifiable"
        return result
    time.sleep(pause)
    e2 = gate_e2(row)
    result["gates"]["E2"] = e2
    if e2["verdict"] == "alias_in_campaigns":
        result["verdict"] = "rejected:alias_in_email_campaign"
        return result
    if e2["verdict"] == "unverifiable":
        result["verdict"] = "excluded:E2_unverifiable"
        return result
    time.sleep(pause)
    h1 = gate_h1(row)
    result["gates"]["H1"] = h1
    if h1["verdict"] == "in_linkedin_campaigns":
        result["verdict"] = "rejected:already_on_linkedin"
        return result
    if h1["verdict"] == "unverifiable":
        result["verdict"] = "excluded:H1_unverifiable"
        return result
    time.sleep(pause)
    m1 = gate_m1(row)
    result["gates"]["M1"] = m1
    if m1["verdict"] != "admitted":
        result["verdict"] = f"excluded:M1_{m1['verdict']}"
        return result
    result["verdict"] = "linkedin_only"
    return result


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=int, default=3,
                    help="how many of the largest complete cells to verify")
    ap.add_argument("--per-cell", type=int, default=40)
    ap.add_argument("--pause", type=float, default=0.15)
    ap.add_argument("--all", action="store_true",
                    help="verify the WHOLE store pool, fully-tagged cells "
                         "first, then everyone else. The untagged ones cannot "
                         "be cohorted today but their provider verdict is "
                         "what says whether sourcing or tagging is the "
                         "constraint")
    ap.add_argument("--out", default="verified_candidates.json")
    args = ap.parse_args(argv)

    pool = survivors()
    cells = collections.defaultdict(list)
    for row in pool:
        if complete(row):
            cells[cell_of(row)].append(row)
    ranked = sorted(cells.items(), key=lambda kv: -len(kv[1]))

    print(json.dumps({
        "pool_after_store_gates": len(pool),
        "with_all_five_axes": sum(len(v) for v in cells.values()),
        "distinct_cells": len(ranked),
        "top_cells": [{"cell": list(k), "n": len(v)} for k, v in ranked[:12]],
    }, indent=1))

    queue = []
    for cell, rows in ranked[:(len(ranked) if args.all else args.cells)]:
        for row in rows[:args.per_cell]:
            queue.append((cell, row))
    if args.all:
        tagged = {(r["record_id"], r["contact_key"]) for _c, r in queue}
        for row in pool:
            if (row["record_id"], row["contact_key"]) not in tagged:
                queue.append((("untagged", row.get("vertical"),
                               row.get("band"), row.get("persona"),
                               SIGNAL_COLD), row))

    verified = []
    for cell, row in queue:
        out = dict(row)
        out.update(verify(row, args.pause))
        out["cell"] = list(cell)
        verified.append(out)
        print(f"  {len(verified):4d}/{len(queue)} {out['verdict']:38s} "
              f"{str(cell[0])[:10]:10s} {str(cell[3])[:14]:14s} "
              f"reqs={boot.CALLS['n']}", file=sys.stderr)

    with open(os.path.join(boot.OUT, args.out), "w",
              encoding="utf-8") as f:
        json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "requests": boot.CALLS, "rows": verified}, f, indent=1)

    tally = collections.Counter(r["verdict"] for r in verified)
    print(json.dumps({"verified": len(verified),
                      "verdicts": tally.most_common(),
                      "requests": boot.CALLS}, indent=1))


if __name__ == "__main__":
    main()
