"""One account's research, as a pack the copy lint can check a claim against.

    from src import packfacts
    pack, unused = packfacts.pack_for(rec)
    copylint.check_batch(leads, {lead_id: pack})

READ ONLY. It reads what is already on the record and returns a new dict. It
writes nothing, reaches no provider and buys nothing.

## WHY IT IS NOT IN `copylint` AND NOT IN `researchpack`

`copylint` is deliberately ignorant of where a pack came from: it is handed
`{"facts": [{"snippet": ...}]}` and asks whether a claim traces. Teaching it
the shape of a queue record would tie the lint to this estate's storage.

`researchpack` builds packs by BUYING them from Apify. This buys nothing: the
estate already holds `rec["research"]`, written by the site crawl, and that is
a pack nobody has been reading. So this is the adapter between the state we
have and the lint we merged, and it is the module both the send path and
`scripts/packfact_check.py` ask.

## IDENTITY, NOT PRESENCE - AND THAT IS THE WHOLE POINT

Measured 2026-09-24: 50 of the 71 job rows the research pilot returned
belonged to a DIFFERENT company, because `companyName` is a text filter and
not an identity match. On five of the eight accounts that returned rows, every
row was somebody else's. Those rows would have put a stranger's open roles
into a client's personalised email, and a presence check - "this account has
research" - calls that account covered.

So a fact is admitted to an account's pack only when it can be shown to be
THAT account's, and `identity_of` states the three answers apart:

    admitted      the fact says whose it is and it is this account's
    refused       the fact says whose it is and it is somebody else's
    unverifiable  the fact does not say, so the question was never asked

The third is not a pass. It is reported separately because "we could not ask"
and "we asked and the answer was no" are different problems with different
fixes, and folding them together reports the second as the first.

## THE PACK IS THE CLAIM LICENCE, SO THE CLIENT'S CSV IS NOT IN IT

OPERATOR DECISION, Zvonimir, 2026-09-27: facts from Productive's own approved
list (the 09-07 CSV) may enter the admitted pack as `CLIENT_SUPPLIED`, with the
source FILE and ROW recorded, and are usable for qualification and strategy.
**A prospect-facing claim still needs a public source or a stored page, never
the CSV alone.**

`pack_for`'s first return value is exactly the list `copylint` and
`sequencegate` license a prospect-facing claim from. Until this decision the
client-CSV facts were appended straight into it, without passing `identity_of`,
so a headcount-growth figure typed into an unverified spreadsheet could ground
an assertion in an email. The seam is therefore that the claim-licensing pack
and the qualification/strategy facts stop being the same list:

    pack["facts"]               claim licence. Identity-admitted research only:
                                a public source or a stored page.
    unused[CLIENT_SUPPLIED]     the client's own facts, with provenance, for
                                qualification and strategy - and for the audit
                                artifact. Never a claim licence.

`unused` is what did NOT license a claim, and why. The qualification and
strategy paths do not read this module at all: `company_facts` on the record is
where that truth canonically lives, and `segments.classify` and `icp.score`
read it directly. `client_supplied_facts` is the PROVENANCE view of the same
canonical state, which is the half those readers cannot express.
"""
import urllib.parse

#: Where a row states its OWN website, across the shapes this estate holds.
#: The jobs actor answers `companyWebsite`, the company actor answers
#: `website`, and the crawler's evidence rows answer neither - because the
#: page they were read from IS the website, which `identity_of` falls back to.
SITE_KEYS = ("companyWebsite", "website", "companyDomain", "domain")

ADMITTED = "admitted"
REFUSED = "refused"
UNVERIFIABLE = "unverifiable"

#: Provenance for a fact that came from the client's own approved list.
#: Sanctioned by the operator's decision of 2026-09-27 (Zvonimir) and recorded
#: in `docs/OPERATING-MODE.md` beside VERIFIED / CLIENT_APPROVED / INFERRED /
#: UNKNOWN. It licenses qualification and strategy. It does NOT license a
#: prospect-facing claim on its own, which is why it is not an identity verdict
#: and why nothing carrying it reaches `pack["facts"]`.
CLIENT_SUPPLIED = "CLIENT_SUPPLIED"

#: The row a fact came from, when the record predates row capture. NOT row 0,
#: and deliberately not a number: a fabricated row number is worse than an
#: honest absence, and `0` has to stay tellable from "we never knew".
UNKNOWN_ROW = "UNKNOWN"

#: The source file, when the record carries no batch at all. Lower case
#: because that is what this estate's already-ingested records hold.
UNKNOWN_SOURCE = "unknown"


def host_of(url):
    """The bare host of a url, or of a bare host. `www.` is not identity."""
    text = str(url or "").strip()
    if text and "//" not in text:
        text = "//" + text
    host = urllib.parse.urlparse(text).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def normalise_domain(domain):
    domain = str(domain or "").strip().lower().lstrip("@")
    return domain[4:] if domain.startswith("www.") else domain


def same_site(value, domain):
    """Is this host the account's own domain, or a subdomain of it?"""
    host, domain = host_of(value), normalise_domain(domain)
    if not host or not domain:
        return False
    return (host == domain or host.endswith("." + domain)
            or domain.endswith("." + host))


def identity_of(row, domain, record_id=None):
    """Whose fact is this: ADMITTED, REFUSED or UNVERIFIABLE.

    THE ONE TEST, APPLIED TO WHATEVER THE ROW CAN ANSWER WITH. A row that
    states its own website is judged on that - the same field
    `researchpack.actors.is_this_company` reads, and the field the 50-of-71
    defect contradicted while `companyName` agreed with it. A row that states
    no website is judged on the host of the page it was read from, which is
    the right test for a site crawl and the only one available for it.

    A POST ON A PLATFORM IS NOT EVIDENCE OF WHOSE POST IT IS. The host of a
    LinkedIn post is LinkedIn's, so the host test cannot admit it and must not
    refuse it either - the row simply does not carry the answer. Identity for
    those is established upstream, where the fact is MADE from a row that does
    carry a website, and a fact that arrives here without it is unverifiable.
    """
    domain = normalise_domain(domain)
    if not domain:
        return REFUSED
    stamped = row.get("record_id")
    if record_id is not None and stamped is not None \
            and str(stamped) != str(record_id):
        return REFUSED
    for key in SITE_KEYS:
        if str(row.get(key) or "").strip():
            return ADMITTED if same_site(row[key], domain) else REFUSED
    host = host_of(row.get("source_url"))
    if not host:
        return UNVERIFIABLE
    return ADMITTED if same_site(host, domain) else UNVERIFIABLE


# company_facts keys the ingest carries from a client CSV.  A fact built
# from one of these names the CSV file and row as its source and is stamped
# CLIENT_SUPPLIED, never verified research - directives section 2 requires a
# real source and section 7 forbids fabricating provenance.
INGEST_FACT_KEYS = frozenset({
    "headline", "industry", "headcount", "employee_range",
    "headcount_growth_12m", "products",
})


def batch_provenance(rec):
    """`(source_file, row)` for the batch row this record was ingested from.

    THE ROW IS THE HALF THAT WAS MISSING. `src/ingest.py` knew it - `run()`
    walks `read_rows(source)` - and threw it away, so a CLIENT_SUPPLIED fact
    could name the file and never the line. It now stores the 1-based ordinal
    of the row within the parsed source on the record's own batch.

    NEVER FABRICATED, AND ABSENCE IS NOT ROW 0. A record ingested before row
    capture has no `row` key and reports `UNKNOWN_ROW`; a record that really
    came from row 0 reports `0`. History is not rewritten either way.

    `batch` is a mapping on records the intake wrote and a BARE STRING on 527
    records in the live store - `report.batch_of` measured that and says so -
    and `.get` straight off it raised AttributeError on every one of them, so
    `pack_for` could not be called at all for those records. A string carries
    the batch's name and no row.
    """
    batch = (rec or {}).get("batch")
    if isinstance(batch, str):
        return (batch.strip() or UNKNOWN_SOURCE), UNKNOWN_ROW
    batch = batch or {}
    source = batch.get("source") or UNKNOWN_SOURCE
    row = batch.get("row", UNKNOWN_ROW)
    return source, (UNKNOWN_ROW if row is None else row)


def client_supplied_facts(rec):
    """Facts from the client CSV the record was ingested from.

    Each entry names the source FILE and the source ROW and carries
    `verification: CLIENT_SUPPLIED` - verified only to the extent the client's
    own approved list is, which is the truth. `UNKNOWN_SOURCE` when the batch
    is absent and `UNKNOWN_ROW` when the row was never captured, never a
    fabricated one of either.

    These are usable for qualification and strategy. They are NOT a claim
    licence, which is why `pack_for` keeps them out of `pack["facts"]` and no
    `source_url` is invented for them: a CSV filename in a field every reader
    treats as a public source is the exact confusion this decision ends.
    """
    facts = (rec or {}).get("company_facts") or {}
    source, row = batch_provenance(rec)
    out = []
    for key in sorted(INGEST_FACT_KEYS):
        val = str(facts.get(key) or "").strip()
        if val:
            out.append({
                "snippet": val,
                "source": source,
                "source_row": row,
                "verification": CLIENT_SUPPLIED,
                "fact_key": key,
            })
    return out


def pack_for(rec):
    """`(pack, unused)` for one record. `unused` says what did not license.

    The pack is `copylint`'s shape - `{"facts": [{"snippet": ...}]}` - so a
    caller never has to know that this estate calls a snippet a `fact`. It is
    the CLAIM LICENCE: identity-admitted research, meaning a public source or a
    stored page, and nothing else.

    `unused` is keyed by the reason a fact is not in that licence - the two
    identity verdicts, plus `CLIENT_SUPPLIED` for the client's own list. The
    operator's decision of 2026-09-27 is the third key: those facts are real,
    are usable for qualification and strategy, carry their file and row, and
    may never ground a prospect-facing assertion on their own.
    """
    rec = rec or {}
    admitted, unused = [], {REFUSED: [], UNVERIFIABLE: [],
                            CLIENT_SUPPLIED: []}
    record_id, domain = rec.get("id"), rec.get("domain")
    for row in rec.get("research") or []:
        if not isinstance(row, dict):
            continue
        snippet = row.get("fact") or row.get("snippet")
        if not str(snippet or "").strip():
            continue
        entry = {"snippet": snippet, "source_url": row.get("source_url"),
                 "published_at": row.get("published_at")}
        verdict = identity_of(row, domain, record_id=record_id)
        if verdict == ADMITTED:
            admitted.append(entry)
        else:
            unused[verdict].append(entry)
    unused[CLIENT_SUPPLIED] = client_supplied_facts(rec)
    return {"facts": admitted}, unused
