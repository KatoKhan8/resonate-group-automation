"""Lane R: the member id is the whole stop, and one source of it is wrong.

Hard rule: `heyreach_lead_id` MUST be `linkedInUserProfile.linkedin_id` - the
NUMERIC LinkedIn member id nested in the profile. The live-validated stop of
2026-09-25 matched on a NUMERIC id; `linkedInUserProfileId` (an `ACoAA...`
string) 404s.

`heyreach.lead_profile()` surfaces a field it also calls `linkedin_id`, and
for a profile that is in NO campaign this lane read one back as

    imp_<24 uppercase characters>

which is neither numeric nor an `ACoAA...` URN. If an enrolment writes THAT
into `heyreach_lead_id`, every future cross-channel stop for that person is
matched on a value the provider has never accepted - and the stop route's own
404 says "the lead is not present in the campaign", which sends the reader
looking in the wrong place entirely.

So: what shapes does each route actually return, and do the two routes agree
for the SAME person?

  A  `/campaign/GetLeadsFromCampaign` -> `member_id` over real campaign rows
  B  `/lead/GetLead` -> `linkedin_id` for those same people, by profile url
  C  do A and B agree, person by person?
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boot      # noqa: E402
import readonly  # noqa: E402

OUT = os.path.join(boot.WORKTREE, "work", "laneR")
# Client campaigns this cohort sits inside. Ids only; no name is recorded.
SAMPLE_CAMPAIGNS = [473854, 429679, 523983]


def shape(value):
    s = str(value or "")
    if not s:
        return "EMPTY"
    if re.fullmatch(r"\d+", s):
        return "numeric"
    if s.startswith("imp_"):
        return "imp_ prefixed"
    if s.startswith("ACoAA"):
        return "ACoAA urn (the value that 404s)"
    return "other"


def main():
    readonly.install(os.path.join(boot.PROD, "config", ".env"))
    readonly.selftest()
    from src.providers import heyreach

    print("=== A: member_id shapes on real campaign rows ===")
    shapes = Counter()
    paired = []
    for cid in SAMPLE_CAMPAIGNS:
        try:
            leads, total = heyreach.campaign_leads(cid, 0, 25)
        except Exception as exc:                        # noqa: BLE001
            print("  %s unreadable: %s" % (cid, type(exc).__name__))
            continue
        local = Counter(shape(r.get("member_id")) for r in leads)
        print("  campaign %-8s rows=%-4d total=%-7s %s"
              % (cid, len(leads), total, dict(local)))
        shapes.update(local)
        for r in leads[:6]:
            if r.get("profile_url"):
                paired.append((cid, r.get("profile_url"), r.get("member_id"),
                               r.get("provider_profile_id")))
    print("\n  overall :", dict(shapes))
    print()

    print("=== B/C: does /lead/GetLead agree with the campaign row? ===")
    agree = disagree = missing = 0
    rows = []
    for cid, url, member_id, prof_id in paired[:12]:
        try:
            prof = heyreach.lead_profile(url)
        except Exception as exc:                        # noqa: BLE001
            print("  GetLead refused (%s)" % type(exc).__name__)
            missing += 1
            continue
        got = prof.get("linkedin_id")
        same = str(got or "") == str(member_id or "")
        agree += bool(same)
        disagree += (not same)
        rows.append({"campaign": cid,
                     "campaign_row_member_id_shape": shape(member_id),
                     "GetLead_linkedin_id_shape": shape(got),
                     "agree": same})
        print("  campaign %-8s GetLeadsFromCampaign=%-22s GetLead=%-22s %s"
              % (cid, shape(member_id), shape(got),
                 "AGREE" if same else "DISAGREE"))
    print("\n  agree=%d disagree=%d unreadable=%d" % (agree, disagree, missing))

    print("\n=== D: the operator's test identity, the one live-validated "
          "stop ===")
    found = None
    for line in open(boot.QUEUE, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        for c in rec.get("contacts") or []:
            if isinstance(c, dict) and c.get("heyreach_lead_id"):
                found = (c.get("heyreach_lead_id"),
                         c.get("heyreach_campaign_id"), c.get("linkedin"))
    if found:
        print("  the ONE contact carrying heyreach_lead_id:")
        print("     stored id shape   : %s" % shape(found[0]))
        print("     campaign          : %s" % found[1])
    else:
        print("  no contact carries heyreach_lead_id")

    print("\n" + readonly.report())
    with open(os.path.join(OUT, "member-id-shapes.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"campaign_row_shapes": dict(shapes), "pairs": rows,
                   "test_identity_shape": shape(found[0]) if found else None},
                  fh, indent=1)


if __name__ == "__main__":
    main()
