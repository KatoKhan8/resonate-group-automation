# Is 4 GB enough — measured

**Short answer: yes for the initial cutover, by a wide margin, and the thing
that ends it is not the number of services. It is the number of RECORDS times
the number of processes holding them at once.**

Host: Hetzner Cloud hel1, 4 GB, ~75 GB disk, Ubuntu 26.04.1 LTS.

---

## 1. THE MEASUREMENT

`store.load()` holds every record in memory. Measured with `tracemalloc` at
three estate sizes, records generated at the production mean of 19,819 bytes:

    records   queue on disk   heap held    peak     bytes/record
        550          7.8 MB     20.6 MB   23.5 MB        37,504
      5,000         70.8 MB    187.3 MB  214.0 MB        37,462
     20,000        283.3 MB    749.2 MB  855.9 MB        37,458

**37,458 bytes of Python heap per record, and it is flat.** The cost is
linear in records over a 36x range, so it extrapolates honestly.

Two things this number is not:

- **It is `tracemalloc`, so it counts Python allocations and not the
  interpreter's own floor** (~15-30 MB per process) or allocator
  fragmentation. Real RSS is higher — assume 1.1-1.3x.
- **It is one process.** Every process that loads the estate pays it
  separately. That is the multiplier that actually decides the answer.

Reproduce: `py -3 <scratch>/memfootprint.py`.

---

## 2. THE CUTOVER, AT TODAY'S ESTATE

`docs/state/QUEUE-MANIFEST.json` says **550 records**.

    11 python processes   ~25 MB floor each        ~275 MB
    estate held by those that load it  550 x 37.5 KB   ~21 MB each
    caddy                                              ~20 MB
    Ubuntu 26.04 + systemd + journald + fail2ban      ~350 MB
    -----------------------------------------------------------
    realistic total, all monitors loaded              ~900 MB

**Under a gigabyte on a 4 GB host.** There is no sizing question at 550
records; there is three gigabytes of headroom and the disk is not close
either — the queue is 8 MB against 75 GB.

---

## 3. WHERE IT STOPS BEING ENOUGH

Leave ~700 MB for the OS and page cache. That leaves roughly **3.3 GB** for
the application, and the formula is:

    records x 37.5 KB x (processes holding the estate at once)

### If every monitor loads the whole estate at once (the worst case)

    records    1 loader   3 loaders   11 loaders
        550      21 MB       62 MB       227 MB      fine
      5,000     187 MB      562 MB      2.06 GB      tight at 11
     10,000     375 MB      1.1 GB      4.12 GB      OVER at 11
     20,000     749 MB      2.2 GB      8.24 GB      OVER at 3+

**So the honest boundary is a band, not a number:**

- **Up to ~5,000 records: comfortable** in every arrangement.
- **5,000-15,000: fine if two or three things load at once, not if eleven
  do.** This is where it stops being a question about the host and becomes a
  question about how many monitors hold a full estate simultaneously — which
  nobody has measured, because on this machine it never mattered.
- **Above ~20,000: 4 GB is the wrong host** for the current design, whatever
  the arrangement. One loader alone is 750 MB.

### The two things that end it sooner than records will

1. **The F6 sourcing service.** `gosom/google-maps-scraper` drives a headless
   browser; with Docker's own daemon that is comfortably **1-1.5 GB while
   running**. On a 4 GB host that is a third of the machine for a service
   that runs nightly. Provision installs Docker **disabled** for this reason.
   If F6 is approved, size the host for it or run sourcing elsewhere.
2. **Two full loads overlapping.** A checkpoint during a walk, a backup taken
   while the web app is serving a report. Two 20k loads is 1.5 GB of
   transient that nothing plans for.

---

## 4. WHAT I WOULD DO

**Cut over on the 4 GB host.** At 550 records it is not close, and the
migration is about getting off a laptop that reboots itself, which is worth
doing now rather than after a resize.

**Then watch one number**: records in `QUEUE-MANIFEST.json`. The status JSON
(queue item 3) already carries stage counts, so the alarm is free — flag at
**10,000 records**, which is roughly a third of the way to the wall and about
as much warning as a resize needs.

**Resizing is not a migration.** Hetzner Cloud resizes a CX/CPX in place with
a reboot: 4 GB to 8 GB is minutes, and with cold-start autostart in place a
reboot is a four-minute event. That is precisely why this is not worth
pre-buying.

**Disk is not the constraint and will not become one.** 20,000 records is
283 MB of JSONL, SQLite is comparable, and fourteen days of retention at that
size is a few gigabytes against 75.

---

## 5. WHAT IS NOT MEASURED HERE, STATED PLAINLY

- **How many processes actually hold a full estate at once.** The table above
  brackets it at 1, 3 and 11 rather than answering it, because the answer
  needs a measurement on a running estate and there has not been one. **This
  is the single number that would tighten this document**, and the place to
  take it is the host after cutover, not here.
- **The web app's per-request footprint** under real reporting load. It was
  not measured; at 550 records it cannot matter.
- **Whether SQLite changes the shape.** `store.load()` materialises the same
  Python objects from either backend, so the heap cost is a property of the
  record model rather than of storage, and the JSONL-vs-SQLite difference
  showed up in write volume and wall clock, not here. Not separately measured,
  and not expected to differ.
