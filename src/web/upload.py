#!/usr/bin/env python3
"""Parsing a CSV of domains, before anything is written.

## Why this is a separate step

`ingest.run` reads a file and commits records in one go. That is right for a
CLI, where the operator chose the file deliberately. It is wrong for a browser,
where the first thing anybody wants to know is *what would this do* - and where
the answer "23 invalid, 41 suppressed, 24 already here" is worth seeing before
5,000 rows land in the queue.

So this parses and reports, and commits only on a second, explicit request.
Every rule it applies is `ingest`'s own: `norm_domain`, `load_suppress` and the
same collision check. It re-implements none of them.

## What it refuses

**A cell that would execute in a spreadsheet.** The uploaded file is
attacker-controlled, and a domain column reading `=IMPORTXML(...)` is a real
attack on whoever opens the export later. `export.py` already guards every cell
this system writes; this guards what it reads, so a formula never gets stored
in the first place.

**A file that is not plausibly a CSV.** Bounded size, decoded as UTF-8 with a
replacement fallback rather than an exception, and a row cap - a browser upload
is the one place where a hostile input arrives by design.
"""
import csv
import io
import re

from .. import (columns, dedupe, hygiene as hygiene_module, identity,
                ingest, linkedin, store)
from . import xlsx

# A 5,000-domain list is about 200 KB. Ten times that is generous and still far
# from a memory problem; beyond it, something is wrong with the file.
MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 200_000

# How long a single free-text cell may be. A CSV is untrusted input and a
# cell has no natural length: a sixty-thousand character company name
# renders a page nobody can scroll, and travels into a provider payload
# and a client PDF on the way.
#
# One number for every free-text field, because the contact columns were
# already bounded here and the company name was not - same file, same
# source, two different answers.
MAX_CELL = 200

# Excel, Google Sheets and LibreOffice all treat these as the start of a
# formula. `src/export.py` guards what this system writes; this refuses to
# store one in the first place.
FORMULA_PREFIXES = ("=", "+", "-", "@")

# Tab and carriage return are the other half of the same trick: a leading
# control character is stripped by the spreadsheet before it decides what the
# cell is, so `<tab>=cmd` and `<tab>+cmd` arrive as formulas. They are checked
# separately because the obvious implementation - `value.lstrip()` then
# `startswith` - removes exactly the characters it is looking for, which is
# how a guard listing them passed a file containing them.
CONTROL_PREFIXES = ("\t", "\r", "\n", "\x00")

# What a domain has to look like before it is stored as one. `norm_domain`
# normalises but does not validate: it turns "cmd|'/c calc'!A1" into "cmd|'"
# and hands it back as a domain, because it was written to clean up URLs
# rather than to reject junk. Enforcing a shape here keeps a value that is
# plainly not a hostname out of the queue, where it would end up in a payload,
# an export or an MX lookup.
# The rule itself lives in `ingest`, so the import path and the discovery
# path cannot drift into two opinions about what a domain is.
HOSTNAME = ingest.HOSTNAME


class UploadRefused(ValueError):
    """The file was rejected. Nothing was parsed and nothing was written."""


def looks_like_formula(value):
    text = str(value or "")
    if text.startswith(CONTROL_PREFIXES):
        return True
    return text.lstrip().startswith(FORMULA_PREFIXES)


# Contact columns, all optional. A domain list is still a domain list; when a
# file does carry people, these are the only two that are *identity* and so
# the only two that can match a row to somebody we have written to before.
# `name` is read for display and can never match anything - see `src/dedupe.py`.
# `title` is here because it is already canonical - `account.contact_card`
# and `dossier` read `contact["title"]` - and it was the one field a lead
# list always carries that the importer threw away. Persona selection and
# claim licensing both need it, and without it a 114-row file of named
# decision makers arrives with no way to tell a CFO from an intern.
#
# Seniority and department are deliberately *not* here. They are not
# canonical contact state anywhere in this system, and adding them through
# an importer would be inventing a second representation of something
# `personas` already derives from the title.
CONTACT_COLUMNS = ("email", "linkedin", "name", "first_name", "last_name",
                   "title")

# The columns that become identity. `contact_identity` reads these,
# and a value cut short here is not a damaged identity but a valid
# one belonging to somebody else.
IDENTITY_COLUMNS = ("email", "linkedin")

# Company-level operational columns that travel with the domain, not the
# contact. These are unmapped by `columns` (it has no opinion about them)
# and would otherwise sit in `contact["source"]` as provenance nobody reads.
# Carried through to `rec["company_facts"]` so the pack and the copy path
# can use them. Each entry: source column normalised -> company_facts key.
#
# TASK-311: headcount growth is the operational signal the homepage lacks -
# an agency that grew 40% in twelve months has a resourcing problem it can
# be written to about. The three columns come from a 51,741-row universe
# that overlaps the packs by only 1,693 of 17,467 domains.
OPERATIONAL_COLUMN_MAP = {
    "companytotalheadcountgrowth12months": "headcount_growth_12m",
    "companyproductandservices": "products_and_services",
    "companyemployee count": "employees",
    "companyemployeecount": "employees",
    "companycompanysize": "company_size",
    "companycompanysizebands": "company_size",
    "companyindustrytags": "industry_tags",
}


def _promote_linkedin_from_source(contact, source):
    """A column called 'Url' that holds a LinkedIn profile is a LinkedIn URL.

    `columns` deliberately refuses to map the header "url" to any canonical
    field - it is too vague to mean one thing, and a company page in the
    LinkedIn slot would merge every employee into one contact. But an
    AI-ARK / ContactOut people-search export puts the profile URL in a
    column called exactly `Url`, and 100% of its rows are LinkedIn profiles.

    The value is checked, not trusted: only a string that
    `linkedin.canonical` accepts as a profile is promoted. A company page,
    a search URL or a truncated share link stays in source provenance where
    it belongs.
    """
    if contact.get("linkedin"):
        return
    for key in ("Url", "URL", "url"):
        candidate = (source or {}).get(key) or ""
        candidate = candidate.strip()
        if not candidate:
            continue
        profile = linkedin.canonical(candidate)
        if profile:
            contact["linkedin"] = profile
            source.pop(key, None)
            return


def _extract_operational_facts(source):
    """Company-level facts from unmapped columns, removed from source.

    Returns a dict of company_facts entries. The keys are removed from
    `source` in place so they do not appear as provenance alongside the
    canonical facts they became.
    """
    if not source:
        return {}
    out = {}
    for normalised, fact_key in OPERATIONAL_COLUMN_MAP.items():
        for src_key in list(source):
            if re.sub(r"[^a-z0-9]+", "", src_key.lower()) == normalised:
                value = (source.pop(src_key) or "").strip()
                if value and fact_key not in out:
                    out[fact_key] = value[:MAX_CELL]
    return out


def contact_identity(contact):
    """The strong identity a row carries, or None.

    Exactly the two `dedupe` treats as identity: a normalised mailbox and a
    canonical profile URL. A name is never identity - two people share one
    and one person has three - so a file of five unnamed rows at one domain
    is five duplicate company rows, not five people.
    """
    email = dedupe.normalise_email((contact or {}).get("email"))
    if email:
        return f"email:{email}"
    profile = linkedin.canonical((contact or {}).get("linkedin"))
    if profile:
        return f"linkedin:{profile}"
    return None

# The delimiters a real export uses. Comma is first so that a tie keeps the
# behaviour every existing file already relies on.
DELIMITERS = (",", ";", "\t", "|")

# Where `csv.DictReader` puts cells past the last header.
RAGGED = "__ragged__"


def _as_csv(grid):
    """A spreadsheet as the CSV the rest of this module already reads.

    One parser for the file, one for the shape. Reading a workbook into the
    same bytes a CSV arrives as means the alias table, the formula guard
    and the hygiene screen cannot behave differently for a spreadsheet -
    which is the only way to be sure they do not.
    """
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(grid)
    return out.getvalue().encode("utf-8")


def sniff(text):
    """Which delimiter makes this file readable.

    Chosen by whether it *works* rather than by counting characters: each
    candidate is used to split the header row, and the one that yields a
    column identifying the company wins, then the one that maps the most
    columns. `csv.Sniffer` guesses from character frequency and is wrong on
    exactly the files that matter - a comma inside a quoted company name in
    a semicolon-delimited export.

    A semicolon export is the default in most of Europe and from a good
    number of CRMs. Before this, every one of them was refused with "no
    column identifies the company", which is true and unhelpful.
    """
    first = (text or "").splitlines()[0] if text else ""
    best, best_score = DELIMITERS[0], -1
    for candidate in DELIMITERS:
        try:
            fields = next(csv.reader([first], delimiter=candidate), [])
        except csv.Error:
            continue
        chosen = columns.resolve(fields)["chosen"]
        score = (100 if columns.DOMAIN in chosen else 0) + len(chosen)
        if score > best_score:
            best, best_score = candidate, score
    return best


def verification_summary(people, history, policy=None):
    """What this file could be written to today, and what the rest costs.

    Three states rather than two, because the difference between them is
    the difference between a bill and no bill:

      `sendable`   we already hold this address and it is cleared
      `known`      we already hold it and it is not
      `new`        we have never seen it

    The cost is what `verification.plan` says one unseen address needs
    under this workspace's policy, multiplied out. It is an upper bound and
    it is a *plan*: nothing here spends anything and the whole import path
    reaches no provider at all.

    Rows with no address are counted separately rather than folded into
    "unverified". A LinkedIn-only person is not an address that failed.
    """
    from .. import verification

    known = (history or {}).get("by_identity") or {}
    counts = {"people": len(people), "with_address": 0, "no_address": 0,
              "sendable": 0, "known": 0, "new": 0}
    for person in people:
        address = dedupe.normalise_email(person.get("email"))
        if not address:
            counts["no_address"] += 1
            continue
        counts["with_address"] += 1
        seen = known.get(f"email:{address}") or []
        if not seen:
            counts["new"] += 1
        elif any(f.get("sendable") for f in seen):
            counts["sendable"] += 1
        else:
            counts["known"] += 1

    # One unseen address, priced once. Every unseen address in a file needs
    # the same steps, so pricing each separately is the same number arrived
    # at slowly.
    ops = verification.plan({"email": "somebody@example.test"}, policy)
    unverified = counts["new"] + counts["known"]
    return {
        **counts,
        "needs_verification": unverified,
        "per_address": verification.exposure(ops),
        "planned_calls": unverified * len([o for o in ops
                                           if o.get("planned")]),
        "max_calls": unverified * len(ops),
        "note": "a plan, not a spend. Nothing in the import path reaches a "
                "provider, and verification is a separate step somebody "
                "starts.",
    }


def parse(data, existing_domains=(), suppress=None, batch=None, client=None,
          history=None, agency=None, policy=None):
    """Parse an uploaded CSV. Returns a report; writes nothing.

    `existing_domains` is what the client already has, so "already in the
    queue" is answered against this client's records rather than globally -
    two clients may legitimately both be talking to the same company.

    `history` is `hygiene.index(repo.records())` - what this workspace has
    already done. Every surviving row is checked against it before anything
    is committed, enriched or made campaign-eligible, because a CSV row
    carries no history and every one of them looks fresh.

    Passing no history leaves the report's `hygiene` key None, which is the
    honest answer when there was nothing to check against, and keeps the CLI
    path exactly as it was.
    """
    if not data:
        raise UploadRefused("the upload was empty")
    if len(data) > MAX_BYTES:
        raise UploadRefused(
            f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")

    # An xlsx is a zip, and its first four bytes say so before anything
    # else has to guess. Converted to CSV rather than parsed a second way:
    # everything below - the alias table, the formula guard, the hygiene
    # screen, the ragged-row report - then applies to a spreadsheet
    # exactly as it applies to a file somebody exported.
    sheet = None
    if xlsx.looks_like_xlsx(data):
        try:
            grid, sheet = xlsx.rows(data)
        except xlsx.NotAWorkbook as e:
            raise UploadRefused(str(e))
        if not grid:
            raise UploadRefused("this workbook's first sheet is empty")
        data = _as_csv(grid)

    text = data.decode("utf-8-sig", errors="replace")
    delimiter = sniff(text)
    # `RAGGED` collects the cells past the last header. Without a restkey
    # they arrive under `None` and were dropped by the `if k` filter below,
    # so a row with more fields than headers lost data and said nothing.
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter,
                            restkey=RAGGED)
    if not reader.fieldnames:
        raise UploadRefused("no header row: a `domain` column is required")

    # Foreign headers, mapped onto canonical fields. No real export uses
    # Resonate's internal column names, and refusing a file for saying
    # "Company Website" was refusing every file anybody actually has.
    resolution = columns.resolve(reader.fieldnames)
    resolution["delimiter"] = delimiter
    if columns.DOMAIN not in resolution["chosen"]:
        found = ", ".join(str(h) for h in reader.fieldnames[:8] if h)
        raise UploadRefused(
            "no column identifies the company. One of these would work: "
            + ", ".join(columns.ALIASES[columns.DOMAIN][:5])
            + ". This file has: " + (found or "no readable headers"))

    suppress = ingest.load_suppress() if suppress is None else suppress
    existing = {str(d).lower() for d in existing_domains}

    def screen(domain, company, contact):
        """This person against everything already done. None if not run.

        Per person, not per company row. The check used to sit after the
        `domain in seen` branch, so on a list with five people at one
        account only the first was ever compared against previous
        outreach, replies and the agency suppression index - and the
        preview said nothing about the other four. The point of a preview
        is to be told before the credits are spent.
        """
        if history is None:
            return None
        return hygiene_module.check(
            {"domain": domain, "company": company,
             **{k: v for k, v in (contact or {}).items() if k != "source"}},
            history, agency=agency)

    # domain -> the entry for that company, so later rows can
    # attach to it rather than being thrown away.
    # `screened` is one verdict per *person*, plus one per company row that
    # carries nobody, and it is what the summary counts.
    seen, rows, excluded, attached, screened, ragged = {}, [], [], [], [], []
    uploaded = 0
    for number, raw in enumerate(reader, start=2):
        if uploaded >= MAX_ROWS:
            raise UploadRefused(f"more than {MAX_ROWS} rows")
        uploaded += 1
        # A row wider or narrower than its header. Reported rather than
        # quietly trimmed or padded: a shifted column is how an email
        # address ends up in the title field, and the operator is the only
        # one who can tell whether it matters.
        if raw.pop(RAGGED, None) is not None:
            ragged.append({"row": number, "reason": "more cells than the "
                                                    "header has columns"})
        elif any(v is None for v in raw.values()):
            ragged.append({"row": number, "reason": "fewer cells than the "
                                                    "header has columns"})
        # Two views of the same row. The formula guard reads the *unstripped*
        # value, because stripping removes the leading tab that makes the
        # trick work - a guard that strips first can never see what it is
        # looking for. Everything after it reads the tidy one.
        untouched, extra = columns.apply(
            {k: (v or "") for k, v in raw.items() if k}, resolution)
        row = {k: v.strip() for k, v in untouched.items()}
        # Columns Resonate has no opinion about. Kept as provenance and
        # never read to decide anything - see `columns.apply`.
        source = {k: v.strip()[:MAX_CELL] for k, v in extra.items()
                  if v and v.strip()}
        value = row.get("domain", "")

        if looks_like_formula(untouched.get("domain", "")):
            excluded.append({"row": number, "domain": value[:80],
                             "reason": "refused: this cell would execute as a "
                                       "formula in a spreadsheet"})
            continue

        domain = ingest.norm_domain(value)
        if not domain:
            excluded.append({"row": number, "domain": value[:80],
                             "reason": "not a usable domain"})
            continue
        if not HOSTNAME.match(domain):
            excluded.append({"row": number, "domain": domain[:80],
                             "reason": "not a usable domain: this is not the "
                                       "shape of a hostname"})
            continue
        if domain in suppress:
            excluded.append({"row": number, "domain": domain,
                             "reason": "suppressed: this is a live account"})
            continue
        company = row.get("company") or domain
        if looks_like_formula(company):
            company = domain
        company = company[:MAX_CELL]

        # Contact columns, guarded exactly as the domain is: a formula in an
        # email column is the same attack on whoever opens the export later.
        contact = {}
        for column in CONTACT_COLUMNS:
            value = row.get(column) or ""
            if value and not looks_like_formula(untouched.get(column, "")):
                # An identity column is refused whole or kept whole. It is
                # never cut.
                #
                # `MAX_CELL` is 200 and an address may be 254, so the
                # 201-254 range is exactly where real long addresses live.
                # Cutting one there does not produce a broken value that
                # fails later - it produces a *different* address, at a
                # different domain, that `normalise_email` accepts. That
                # becomes the contact's canonical identity, is counted as
                # an address needing verification, and is committed. An
                # existing test reasons that "a truncated address is
                # simply not an address", which holds only when the cut
                # lands before the `@`.
                if column in IDENTITY_COLUMNS and len(value) > MAX_CELL:
                    excluded.append({
                        "row": number, "domain": domain,
                        "reason": f"the {column} in this row is longer than "
                                  f"{MAX_CELL} characters; it was not "
                                  "shortened, because a shortened address "
                                  "is a different address"})
                    continue
                contact[column] = value[:MAX_CELL]

        # A column called "Url" that holds a LinkedIn profile is promoted
        # to the contact's linkedin field. The value is checked, not trusted.
        _promote_linkedin_from_source(contact, source)
        # Company-level operational facts (headcount growth, products, etc.)
        # are extracted from source provenance and travel with the domain.
        op_facts = _extract_operational_facts(source)

        # A domain is a company; a row is a person at one. Five rows at
        # `acme.test` are five contacts on one account, not one account and
        # four discarded duplicates - which is what this used to do, and
        # what nobody uploading a lead list expects.
        #
        # Only *strong* identity makes a row a distinct person: a
        # normalised mailbox or a canonical profile URL. A name is never
        # identity here, for the same reason it is never identity in
        # `dedupe` - two people share one and one person has three.
        if source:
            contact["source"] = source
        person = contact_identity(contact)

        if domain in seen:
            first = seen[domain]
            if person is None:
                # Nothing distinguishes this row from the one already
                # taken. That is a duplicate company row, and still is.
                excluded.append({"row": number, "domain": domain,
                                 "reason": "duplicate row in this file"})
                continue
            if person in first["identities"]:
                excluded.append({"row": number, "domain": domain,
                                 "reason": "duplicate contact in this file"})
                continue
            first["identities"].add(person)
            joined = dict(contact, row=number)
            verdict = screen(domain, first["company"], contact)
            if verdict is not None:
                joined["hygiene"] = verdict
                screened.append({"row": number, "domain": domain,
                                 "company": first["company"],
                                 "who": (contact.get("name")
                                         or contact.get("email") or domain),
                                 "verdict": verdict})
            first["contacts"].append(joined)
            # Operational facts from a later row at the same domain fill in
            # fields the first row did not carry. First writer wins for each
            # key, matching the contact merge semantics.
            if op_facts:
                existing_facts = first.setdefault("company_facts", {})
                for k, v in op_facts.items():
                    existing_facts.setdefault(k, v)
            attached.append({"row": number, "domain": domain,
                             "reason": "another person at a company already "
                                       "in this file"})
            continue

        entry = {"domain": domain, "company": company,
                 "client": client, "batch": batch, "row": number,
                 "contacts": [dict(contact, row=number)] if person else [],
                 "identities": {person} if person else set()}
        if op_facts:
            entry["company_facts"] = op_facts
        seen[domain] = entry

        # The hygiene verdict travels with the row rather than removing it.
        # An operator who cannot see why a row is not cold-eligible cannot
        # tell a wrong hold from a right one.
        verdict = screen(domain, company, contact)
        if verdict is not None:
            entry["hygiene"] = verdict
            if entry["contacts"]:
                entry["contacts"][0]["hygiene"] = verdict
            screened.append({"row": number, "domain": domain,
                             "company": company,
                             "who": (contact.get("name") or contact.get("email")
                                     or domain),
                             "verdict": verdict})

        fresh = verdict is None or verdict["verdict"] == hygiene_module.FRESH
        if domain in existing and fresh and not entry["contacts"]:
            # Already here, adding nobody, and nothing else to say about it.
            # Where hygiene *does* have something to say, the row is kept so
            # it can be read.
            #
            # `not entry["contacts"]` is the third condition and it was
            # missing. A contact-level list re-uploaded with new people at a
            # company already in the queue had every one of those rows
            # dropped under "this client already has this domain" - which is
            # true of the company and false of the person, and they were
            # gone with a reason that did not describe what was lost. The
            # duplicate person is not a problem here: `commit` merges on
            # identity and adds only who is genuinely new.
            excluded.append({"row": number, "domain": domain,
                             "reason": "this client already has this domain"})
            seen.pop(domain, None)
            # It is not in the list any more, so it is not in the count of
            # what the list contains.
            screened[:] = [s for s in screened if s["row"] != number]
            continue

        rows.append(entry)

    # The sets were working state. They do not serialise and nothing
    # downstream needs them.
    for entry in rows:
        entry.pop("identities", None)

    return {
        "batch": batch,
        "client": client,
        # What each column was taken to mean, so an operator can see the
        # decision rather than discover it in the data.
        "mapping": resolution,
        "mapping_notes": columns.describe(resolution),
        "unmapped_columns": resolution["unmapped"],
        "uploaded": uploaded,
        "unique": len(rows),
        "invalid": sum(1 for e in excluded
                       if "usable domain" in e["reason"] or "formula" in e["reason"]),
        "duplicates": sum(1 for e in excluded
                          if "duplicate row" in e["reason"]),
        "duplicate_contacts": sum(1 for e in excluded
                                  if "duplicate contact" in e["reason"]),
        # People attached to a company another row already introduced. Not
        # an exclusion - reported separately because "4 rows were dropped"
        # and "4 more people joined an account" are opposite outcomes.
        "additional_contacts": len(attached),
        "attached": attached,
        # Rows whose shape did not match the header. Counted separately
        # from `invalid`: a ragged row is usually still imported, and
        # saying "12 rows were malformed" about rows that were kept would
        # be its own lie.
        "ragged": ragged,
        "ragged_rows": len(ragged),
        "delimiter": delimiter,
        # Which sheet was read. `None` for a CSV. Named because a workbook
        # whose leads are on the second tab imports the first one, and the
        # only way to notice is to be told which.
        "sheet": sheet,
        "contacts": sum(len(r.get("contacts") or []) for r in rows),
        "suppressed": sum(1 for e in excluded if "suppressed" in e["reason"]),
        "existing": sum(1 for e in excluded if "already has" in e["reason"]),
        "rows": rows,
        "excluded": excluded,
        # What could be written to today, and what the rest would cost.
        # None when there was no history to compare against, which is a
        # different statement from "none of them are known".
        "verification": (verification_summary(
            [c for r in rows for c in r.get("contacts") or []],
            history, policy) if history is not None else None),
        # What the hygiene pass found, if it ran. None means it did not run,
        # which is a different statement from "it ran and found nothing".
        # One verdict per person, not per company row. `screened` is what
        # it counts, and its total is people rather than companies.
        "hygiene": (hygiene_module.summarise(
            [s["verdict"] for s in screened]) if history is not None
            else None),
        "screened": screened,
        # Nothing has been written. The caller decides.
        "committed": False,
    }


def commit(repo, parsed, lane="domains"):
    """Write the parsed rows as queue records. Client-scoped throughout."""
    if parsed.get("committed"):
        raise UploadRefused("this batch has already been committed")
    # The preview is held per session, not per workspace, so a member of two
    # workspaces could parse in one, switch, and commit here. Everything below
    # scopes to `repo` - `repo.records()` for the merge, `repo.client` on each
    # new record - so those rows would be written into a workspace whose
    # suppression and engagement history they were never checked against.
    if parsed.get("client") != repo.client:
        raise UploadRefused(
            "this preview was parsed in another workspace; "
            "re-upload the file here")
    records = []
    # One record per company, because the account is the unit of outreach.
    #
    # A re-imported master list is the normal case, not an edge: the same
    # spreadsheet comes back next month with more people on it. `parse`
    # deliberately keeps a row whose hygiene verdict has something to say -
    # so the operator can read *why* it is not cold-eligible - which means
    # a suppressed company reaches this function by design.
    #
    # What must not happen is a second skeleton for a company that already
    # exists. `store.new_record` produces a record with no suppression, no
    # events and no unsubscribed flags, and before the id de-collision
    # above, `save_records` upserted it straight over the real one: a
    # company that had asked to stop came back clean, with nothing
    # anywhere recording that it ever asked. With de-collision it stops
    # overwriting and starts duplicating instead, which is a different
    # wrong answer - two records for one domain, one of them suppressed
    # and one of them not.
    #
    # So an existing account is merged into, never rebuilt. Suppression,
    # events, state and per-contact flags are the account's own history
    # and this function has nothing to say about them; the only thing an
    # import may add is people.
    mine = {}
    for existing in repo.records():
        if existing.get("domain"):
            mine.setdefault(str(existing["domain"]).lower(), existing)
    # The id namespace in queue.jsonl is global, even though visibility is
    # not, so collisions are resolved against every id in the file rather
    # than against this client's.
    #
    # `slug` truncates at 40 characters and `ingest.run` has always carried
    # a de-collision loop after it; this path had the truncation and not
    # the loop. Two genuinely different companies -
    # northwind-industrial-holdings-europe-gmbh.test and the same name
    # under .de - produce one id, and `save_records` upserts by id, so one
    # of them was silently discarded between the preview and the queue
    # while the audit entry recorded that both had been written.
    #
    # Across clients it was worse rather than better: `save_records` only
    # replaces rows it owns, so importing a domain another workspace
    # already holds appended a *second* row with the same id. Every
    # id-addressed route then refused the importing client's own record,
    # because `store.get` finds the other one first. Two clients talking
    # to the same company is the normal multi-tenant case, and
    # `upload.parse` says so in its own docstring.
    taken = {r.get("id") for r in store.load()}
    for row in parsed["rows"]:
        people = [{k: v for k, v in person.items() if k != "row"}
                  for person in row.get("contacts") or []]

        held = mine.get(str(row["domain"]).lower())
        if held is not None:
            if people:
                known = {identity.identity_of(c)
                         for c in held.get("contacts") or []}
                added = [p for p in people
                         if identity.identity_of(p) not in known]
                if added:
                    held["contacts"] = identity.assign_keys(
                        list(held.get("contacts") or []) + added)
            # Operational facts from the import fill in company_facts fields
            # the existing record did not have. First writer wins per key.
            row_facts = row.get("company_facts") or {}
            if row_facts:
                existing_facts = held.setdefault("company_facts", {})
                for k, v in row_facts.items():
                    existing_facts.setdefault(k, v)
            records.append(held)
            continue

        rid = base = ingest.slug(f"{row['domain']}")
        suffix = 2
        while rid in taken:
            rid = f"{base}-{suffix}"
            suffix += 1
        taken.add(rid)
        rec = store.new_record(rid, lane, repo.client, row["company"],
                               row["domain"])
        rec["batch"] = parsed["batch"]
        # The people the file carried. This used to be dropped on the
        # floor: the columns were read, used for hygiene matching, and then
        # discarded, so a contact-level list committed as companies with no
        # contacts at all. `assign_keys` gives each one a deterministic id
        # and handles collisions.
        if people:
            rec["contacts"] = identity.assign_keys(people)
        # Company-level operational facts from the import (headcount growth,
        # products and services, employee count). TASK-311.
        row_facts = row.get("company_facts") or {}
        if row_facts:
            rec["company_facts"].update(row_facts)
        records.append(rec)
    repo.save_records(records)
    # Audited like every other durable write. This was the one that was
    # not: an import is the largest single change anybody makes to a
    # workspace, and the audit log did not record that it happened, who
    # did it, or how much of it there was.
    repo.audit("batch.committed", "batch", parsed.get("batch"),
               after={"companies": len(records),
                      "contacts": sum(len(r.get("contacts") or [])
                                      for r in records)},
               reason="imported from a workbook" if parsed.get("sheet")
                      else "imported from a file")
    parsed["committed"] = True
    return records


# ------------------------------------------------------- multipart parsing
#
# `cgi.FieldStorage` was removed in Python 3.13, and the repository takes no
# third-party dependencies, so the small amount of multipart this application
# needs is parsed here. It handles exactly one shape - a browser posting a form
# with some text fields and one file - and refuses anything it does not
# recognise rather than guessing.

def _boundary_of(content_type):
    for part in str(content_type or "").split(";"):
        key, _, value = part.strip().partition("=")
        if key.lower() == "boundary":
            return value.strip('"')
    return None


def parse_multipart(body, content_type):
    """(fields, files) from a multipart/form-data body.

    Values are decoded as UTF-8 with replacement: a browser sends UTF-8, and a
    decoding error on a form field is not worth a 500 when the field is about
    to be validated anyway. File contents stay bytes.
    """
    boundary = _boundary_of(content_type)
    if not boundary:
        raise UploadRefused("multipart body with no boundary")
    marker = ("--" + boundary).encode("utf-8")

    fields, files = {}, {}
    for chunk in body.split(marker):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        head, _, data = chunk.partition(b"\r\n\r\n")
        if not _:
            continue
        disposition = ""
        for line in head.decode("utf-8", "replace").split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                disposition = line
                break
        if not disposition:
            continue

        name = filename = None
        for part in disposition.split(";")[1:]:
            key, _, value = part.strip().partition("=")
            value = value.strip('"')
            if key == "name":
                name = value
            elif key == "filename":
                filename = value
        if not name:
            continue
        data = data.rstrip(b"\r\n")
        if filename is not None:
            files[name] = data
        else:
            fields[name] = data.decode("utf-8", "replace")
    return fields, files
