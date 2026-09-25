"""Lane R: the five gates, every one of them a PROVIDER read, fail-closed.

    usage:  python scripts/laneR/gates.py [n] [seed]
            n = 0 runs the whole cohort (the foreground's out-of-hours run)

THE POPULATION IS THE INVERSE OF LANE P'S. Lane P wanted people in NO email
campaign; this lane wants exactly the people who ARE in 491-498, and pairs
them on LinkedIn. So the email gate is inverted and a new one appears: these
people have been emailed, and some of them have already answered.

    X1  email state       `GET /leads/{id}` -> `lead_campaign_data`, filtered
                          to 491-498. `replied` -> EXCLUDE, absolutely and
                          with no exemption. `stopped` -> EXCLUDE: the status
                          does not say whether we stopped them, they
                          unsubscribed, or the provider stopped them ON A
                          REPLY (ISSUE-035). Not readable -> UNVERIFIABLE.
    X2  outside estate    the same array, entries OUTSIDE 491-498. Any entry
                          is a client campaign our store does not know about.
    H1  linkedin collision `/campaign/GetCampaignsForLead`. ANY campaign,
                          ours or the client's -> EXCLUDE. A refusal is
                          UNVERIFIABLE, never an absence.
    M1  identity          `/lead/GetLead`. Surname or company disagrees ->
                          REFUSED. Provider will not name one -> UNVERIFIABLE.
                          THIS READ ALSO YIELDS `linkedin_id`, which is the
                          `leadMemberId` every future stop is matched on.
    A1  account rule      `collision.check_account` + `account_policy`, and
                          the client's own `fatigue.account.max_active_contacts`.

UNVERIFIABLE IS NOT A PASS ANYWHERE. Every verdict starts at `unverifiable`
and only positive evidence moves it.

Reads only: `readonly.install` seals the transport and `readonly.selftest`
proves the seal refuses `StopLeadInCampaign` before the first read is made.
"""
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402

OUT = os.path.join(boot.WORKTREE, "work", "laneR")
COHORT = {str(c) for c in range(491, 499)}
WORKSPACE = "10"

ADMITTED, REFUSED, UNVERIFIABLE = "admitted", "refused", "unverifiable"

# Email membership words that end a person's candidacy. `replied` is the
# obvious one. `stopped` is the one that matters: ISSUE-035 - our own stop and
# a reply-triggered stop are the same word, and the reply_watch_loop stops a
# lead ON A REPLY, so a `stopped` row is as likely to be somebody who answered
# as somebody we withdrew. Treating it as free capacity is exactly the second
# message to somebody who already replied.
DISQUALIFYING = {"replied", "stopped", "bounced", "unsubscribed"}
PAIRABLE = {"in_sequence", "sequence_finished", "sending_paused"}


def norm(text):
    return " ".join(str(text or "").strip().lower().split())


def company_tokens(text):
    stop = {"ltd", "limited", "inc", "llc", "gmbh", "the", "group", "co",
            "company", "agency", "studio", "and", "&", "bv", "b.v.", "plc",
            "sa", "srl", "ab", "as", "oy", "pty"}
    toks = {t.strip(".,-") for t in norm(text).replace("/", " ").split()}
    return {t for t in toks if t and t not in stop and len(t) > 2}


def m1_verdict(store_row, profile):
    """admitted / refused / unverifiable for 'is this profile that person'.

    The same three-answer shape `packfacts.identity_of` uses, and the same
    polarity: the provider declining to name a side is UNVERIFIABLE, which
    excludes; only agreement admits.
    """
    if not isinstance(profile, dict) or not profile:
        return UNVERIFIABLE, "the provider returned no profile"
    p_last = norm(profile.get("lastName"))
    s_last = norm(store_row.get("last_name"))
    if not p_last or not s_last:
        return UNVERIFIABLE, "a surname is missing on one side"
    if p_last != s_last:
        return REFUSED, "surname disagrees"
    p_co = profile.get("companyName") or ""
    s_dom = norm(store_row.get("domain")).split(".")[0]
    if not norm(p_co):
        return UNVERIFIABLE, "the provider names no company for this profile"
    if not s_dom:
        return UNVERIFIABLE, "the store holds no domain for this record"
    if company_tokens(p_co) & company_tokens(s_dom) or s_dom in norm(
            p_co).replace(" ", ""):
        return ADMITTED, "surname and company both agree"
    return REFUSED, "company disagrees"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20260925
    pause = float(os.environ.get("LANER_PAUSE", "0.15"))

    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()
    print("seal ok: StopLeadInCampaign and AddLeadsToCampaignV2 both refused "
          "before the first read.\n")

    from src.providers import bison, heyreach
    from src import collision

    rows = json.load(open(os.path.join(OUT, "cohort-491-498.json"),
                          encoding="utf-8"))["rows"]
    pool = [r for r in rows if r["bison_lead_id"] and r["profile_url"]]
    random.Random(seed).shuffle(pool)
    sample = pool if n <= 0 else pool[:n]

    print("cohort with bison_lead_id AND a /in/ profile url : %d" % len(pool))
    print("sampled                                          : %d\n"
          % len(sample))

    v = Counter()
    out = []
    by_domain = defaultdict(list)

    for i, r in enumerate(sample, 1):
        rec = {"record_id": r["record_id"], "domain": r["domain"],
               "verdict": UNVERIFIABLE, "stage": "start",
               "member_id": None}

        # ---- X1 / X2 : email state, from the provider -------------------
        rec["stage"] = "X1"
        try:
            data = bison.lead(int(r["bison_lead_id"]))
            data = data.get("data") if isinstance(data.get("data"), dict) \
                else data
            entries = data.get("lead_campaign_data") or []
        except Exception as exc:                       # noqa: BLE001
            rec["verdict"] = "excluded:X1_unverifiable"
            rec["why"] = "email state unreadable: %s" % type(exc).__name__
            v[rec["verdict"]] += 1
            out.append(rec)
            continue
        mine = [e for e in entries if str(e.get("campaign_id")) in COHORT]
        outside = [e for e in entries
                   if str(e.get("campaign_id")) not in COHORT]
        rec["cohort_statuses"] = sorted({norm(e.get("status")) for e in mine})
        rec["n_outside_campaigns"] = len(outside)
        if not mine:
            rec["verdict"] = "excluded:X1_not_in_cohort"
            rec["why"] = "the provider does not place this lead in 491-498"
            v[rec["verdict"]] += 1
            out.append(rec)
            continue
        bad = set(rec["cohort_statuses"]) & DISQUALIFYING
        if bad:
            rec["verdict"] = "excluded:X1_%s" % sorted(bad)[0]
            rec["why"] = ("email membership reads %s; a second channel to "
                          "this person is not cold" % sorted(bad))
            v[rec["verdict"]] += 1
            out.append(rec)
            continue
        if not set(rec["cohort_statuses"]) & PAIRABLE:
            rec["verdict"] = "excluded:X1_unknown_status"
            rec["why"] = "status %s has no verified meaning here" % (
                rec["cohort_statuses"],)
            v[rec["verdict"]] += 1
            out.append(rec)
            continue
        if outside:
            v["note:also_in_client_campaign"] += 1

        # ---- H1 : already on LinkedIn, anywhere in the estate ------------
        rec["stage"] = "H1"
        try:
            camps, _tot = heyreach.campaigns_for_lead(r["profile_url"])
        except Exception as exc:                       # noqa: BLE001
            rec["verdict"] = "excluded:H1_unverifiable"
            rec["why"] = ("heyreach would not answer for this profile (%s); "
                          "a refusal is not an absence"
                          % type(exc).__name__)
            v[rec["verdict"]] += 1
            out.append(rec)
            continue
        rec["n_linkedin_campaigns"] = len(camps)
        if camps:
            rec["verdict"] = "excluded:H1_already_on_linkedin"
            rec["why"] = "already in %d LinkedIn campaign(s)" % len(camps)
            v[rec["verdict"]] += 1
            out.append(rec)
            continue

        # ---- M1 : is this profile that person, and the MEMBER ID ---------
        rec["stage"] = "M1"
        try:
            profile = heyreach.lead_profile(r["profile_url"])
        except Exception as exc:                       # noqa: BLE001
            rec["verdict"] = "excluded:M1_unverifiable"
            rec["why"] = "profile unreadable: %s" % type(exc).__name__
            v[rec["verdict"]] += 1
            out.append(rec)
            continue
        verdict, why = m1_verdict(r, profile)
        rec["m1"] = verdict
        rec["why"] = why
        # THE MEMBER ID. `linkedInUserProfile.linkedin_id`, which `lead_profile`
        # surfaces as `linkedin_id`. NOT `linkedInUserProfileId`: that is the
        # value HeyReach support named and it 404s on StopLeadInCampaign.
        rec["member_id"] = profile.get("linkedin_id")
        if verdict != ADMITTED:
            rec["verdict"] = "excluded:M1_%s" % verdict
            v[rec["verdict"]] += 1
            out.append(rec)
            continue
        if not rec["member_id"]:
            rec["verdict"] = "excluded:M1_no_member_id"
            rec["why"] = ("the profile carries no linkedin_id, so no future "
                          "stop could match this person")
            v[rec["verdict"]] += 1
            out.append(rec)
            continue

        rec["verdict"] = "passes:person_gates"
        v[rec["verdict"]] += 1
        by_domain[r["domain"]].append(rec)
        out.append(rec)
        if pause:
            time.sleep(pause)
        if i % 10 == 0:
            print("  ... %d/%d, %d provider requests"
                  % (i, len(sample), readonly.total()))

    print("\n=== person gates ===")
    for k, c in v.most_common():
        print("  %-42s %d" % (k, c))

    # ---- A1 : the account rule, over the domains that got this far -------
    print("\n=== account gate, over %d surviving domain(s) ==="
          % len(by_domain))
    acct = Counter()
    accounts = {}
    for domain in sorted(by_domain):
        try:
            a = collision.check_account(domain, expect_workspace=WORKSPACE)
            decision, why = collision.account_policy(a)
        except Exception as exc:                        # noqa: BLE001
            decision, why = "HOLD", "unreadable: %s" % type(exc).__name__
            a = {}
        accounts[domain] = {"decision": decision, "why": why,
                            "anyone_in_sequence": a.get("anyone_in_sequence"),
                            "emails_sent_total": a.get("emails_sent_total"),
                            "leads": a.get("leads"),
                            "survivors_here": len(by_domain[domain])}
        acct[decision] += 1
    for k, c in acct.most_common():
        print("  %-12s %d accounts" % (k, c))
    reasons = Counter(x["why"].split(";")[0][:70]
                      for x in accounts.values())
    print("\n  why:")
    for k, c in reasons.most_common():
        print("    %-72s %d" % (k, c))

    allowed = [d for d, x in accounts.items() if x["decision"] == "allow"]
    print("\n  people behind ALLOW accounts : %d"
          % sum(len(by_domain[d]) for d in allowed))

    print("\n" + readonly.report())
    path = os.path.join(OUT, "gates-sample.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"n": len(sample), "seed": seed, "pool": len(pool),
                   "person_gates": dict(v), "account_gates": dict(acct),
                   "accounts": accounts, "rows": out,
                   "provider_requests": readonly.total()}, fh, indent=1)
    print("wrote", path)


if __name__ == "__main__":
    main()
