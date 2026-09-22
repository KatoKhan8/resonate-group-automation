# Which provider actually honours industry + size + geo — measured, 2026-09-22

Operator decision B asked for this measurement, and it decides which route
tomorrow's client export is built from. **ContactOut wins, decisively, and it
is free to ask.** No company identifiers appear below: the guard forbids them
in tracked files and the finding does not need them.

---

## The verdict in one table

| route | industry | size | geo | cost to ask |
|---|---|---|---|---|
| **ContactOut `people-count`** | honoured | honoured | honoured | **free** |
| **ContactOut `company-search`** | honoured | honoured | honoured | 1 credit per company returned |
| AI ARK `company_search` | **INERT** | n/a | **INERT** | paid |

## The measurement, and why it is conclusive

**A filter is honoured only if changing it changes the answer.** That is the
whole test, and it is the test AI ARK's company search failed.

`people-count` is free, so all three dimensions were varied one at a time from
one baseline:

    Advertising Services · 51-200 staff · United Kingdom     76,476
      size    -> 10,001+                                     30,725
      industry-> Banking                                     48,286
      geo     -> Germany                                      2,981

Every dimension moves the count independently and in the direction it should:
a bigger size bucket is a different population, a different industry is a
different population, and Germany is a much smaller advertising market than
the UK. **Three filters, three responses, no coincidence.**

`company-search` was then asked the company-shaped question the export needs,
with `hq_only`. Twenty-five rows came back and **all twenty-five** carried
industry `Advertising Services`, size bucket `51`, and a GB headquarters.
Not "mostly" - every row.

## What AI ARK's company search did instead

Recorded in the afternoon handoff and not re-litigated here:
`companyIndustry` and `companyLocation` are **accepted and inert**. Filtered
and unfiltered pages returned identical `totalElements` (72,657,969),
byte-identical row hashes, and the same first rows across all four filter
combinations. A filter that changes nothing cannot partition a 72.6M-row
corpus, which is why the country × industry × headcount slicing plan was
unreachable by that route.

**This is a capability difference, not a tuning difference.** No parameter
spelling makes an inert filter partition.

## What this licenses

Tomorrow's candidate set is sourced through **ContactOut company search**,
which is also where the standing provider order already puts it - ContactOut
first, for everything it can return. The route was never the exotic one; it
was first in the order the whole time, and the sourcing that produced the
1,508 went around it.

Target shape, per the operator: advertising, design, digital, PR and software
services, **20 to 1,000 staff**, allowed geos only. In ContactOut's buckets
that is `11_50`, `51_200`, `201_500` and `501_1000` - and note that `11_50`
straddles the 20 floor, so the floor still has to be applied on the returned
`employees` figure rather than assumed from the bucket.

**Counting is free, so the shape is measured BEFORE any credit is spent.**
Every slice gets a `people-count` first; `company-search` is called only for
slices whose count says they are worth returning. That is the progressive
shape the routing policy already requires, and here it costs nothing to obey.

## The trap this leaves behind

`company-search` charges **one credit per company returned**, so an unbounded
page walk is an unbounded spend. Spend is reported rather than gated under the
2026-09-21 amendment, which makes the discipline ours to keep rather than the
gate's: count first, slice to a size worth buying, and never re-buy a domain
the estate already holds.
