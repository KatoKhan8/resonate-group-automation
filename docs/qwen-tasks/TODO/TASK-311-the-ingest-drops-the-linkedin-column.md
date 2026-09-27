PRIORITY: P0
SIZE: M
DEPENDS:

# TASK-311 — the ingest drops the LinkedIn column, and the operational signal with it

Operator decision, 2026-09-25 evening. **Two source files carry columns the
ingest silently discards, and one of them is the reason a ContactOut discovery
run was nearly bought for data we already had.**

## MEASURED BEFORE DISPATCH — do not re-derive

    work/Productive/productive_ICP_safe_to_send (1).csv
      33,887 rows. Column `Url` is a LinkedIn profile on 100.0% of them.
      33,445 also carry `Work Email`.
      THIS IS WHERE 503/504/505 CAME FROM: 250 of 250 leads in 503 match by
      email, and every one has a profile URL.
      Shape: Url, First Name, Last Name, Job Title, Headline, Company,
      Industry, Location, Work Email, Work Email Status - an AI-ARK /
      ContactOut people-search export.

    work/Software_Agencies_All_Geo_cleaned - Sheet1.csv
      51,741 rows, 100% LinkedIn coverage across `LinkedIn` and
      `LinkedIn_URL_Repaired`. 27,293 US. 20,544 distinct domains.
      ALSO CARRIES, and nothing reads them:
        Company_Total_headcount_growth_12_months
        Company_Product_and_Services
        Company_Employee_Count, Company_Size, Company_Industry_Tags
      Overlaps our packs by only 1,693 of 17,467 domains, so it is a
      SEPARATE universe rather than the source of the packs.

## What to build

**1. Carry the LinkedIn URL through the ingest, for both files.** It is a
column that already exists in the input and is dropped on the way in. Bind it
onto the contact so `channels.linkedin_verdict` can read it and the
cross-channel enrolment can use it. Report coverage per file after.

**2. Add the operational columns to the pack**, from the 51,741-row file:
headcount growth over 12 months, products and services, employee count.

**WHY THIS MATTERS MORE THAN IT SOUNDS.** Ten leads were run through the full
copy path on 2026-09-25 and 5 were HELD because the research supported no
opening line. The packs are site copy - what agencies say about themselves on
their own homepages - and almost none of it touches how they run projects.
**Headcount growth is exactly the signal the homepage lacks**: an agency that
grew 40% in twelve months has a resourcing and margin problem it can be
written to about, and that is a fact rather than an assumption.

## Rules

- **No new spend.** Every column named here is already in a file on disk. If
  you find yourself calling a provider, stop and say why.
- A LinkedIn value that is not a profile URL is NOT a profile. Company pages,
  search URLs and truncated share links all appear in these columns; check the
  shape rather than trusting non-emptiness. 15 of 805 values in an earlier
  cohort held something that was not a profile.
- Do not overwrite a URL already bound to a contact from another source
  without saying which won and why.
- `work/` is gitignored and holds real prospect data. It stays local.

## Acceptance, in one command

    py -3 -c "import sys;sys.path.insert(0,'.');from src import store;\
    rs=store.load();c=[x for r in rs for x in (r.get('contacts') or [])];\
    n=sum(1 for x in c if 'linkedin.com/in/' in str(x.get('linkedin') or '').lower());\
    print(n,'of',len(c),'contacts carry a LinkedIn profile');assert n"

plus the coverage numbers per file in your report, and the pack fields visible
on a rebuilt pack for one domain you name.
