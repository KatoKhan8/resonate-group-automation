# Merge request — Phase C, increment 1: domains and language

**For the production session.** Branch `slack-agent` at `a71cdee1`, pushed.
Not merged, not pushed to master — the three-session rule took effect
partway through today and this is the first increment delivered under it.

Built from one real message in `#productive-resonate-outbound`.

---

## 0. WHAT THIS TOUCHES THAT IS YOURS

    src/providers/slack.py     +1 READ: thread_parent()

Everything else is agent-owned (`src/slack*.py`,
`scripts/slack_agent_loop.py`, the slack tests). No `config/.env`, no
`*_watch_loop.py`, no `work/`.

`thread_parent` calls `conversations.replies` with `limit=1` and returns
`{user, text, ts}` or `None`. It exists because a relayed question is the
thread's FIRST message, which the agent was never delivered — it was not
mentioned in it. Without the read the alternative is asking a person to
paste their own question back, which is a chore rather than a relay.

It needs `channels:history` (public) or `groups:history` (private). Missing
either, Slack answers `missing_scope`, the function returns `None`, and the
agent says so in the thread and names the scope rather than answering the
trigger phrase as though it were the question.

**Checked for overlap before starting:** no branch ahead of master touches
`src/providers/slack.py`, `src/slackconversation.py`,
`src/slackagenttools.py`, `scripts/slack_agent_loop.py`, `src/store.py` or
`tests/test_invariants.py`.

---

## 1. THE MESSAGE THIS IS BUILT FROM

`#productive-resonate-outbound`, 2026-09-22 09:18 CEST, from an external
Productive person to Jelena and Tina by name:

> bok @Jelena i @Tina, kako ste? Trebam od vas popis domena s kojih šaljete
> mailove u email kampanjama, možete tu pasteati popis, u thread

At 11:17 a 194KB CSV of every sender was attached. At 11:18 the next
message in the thread was:

> <sending-domain>.example.test, kakva je ovo domena?

**The question was about domains and the answer was addresses.** That gap
is what this increment closes.

---

## 2. `sending_domains`

Client and internal scope. For the bound workspace: every sending domain
behind that workspace's **authorized** senders, grouped by sender human,
with mailboxes per domain and whether the domain carried sends in the last
seven days.

Live against the real estate: **69 distinct domains, 159 mailboxes, 8
people** — and `<sending-domain>.example.test` is there, under two of them.

- **Domains only.** `email_address` and the queue row's `sender_email` are
  read to take the domain and dropped. A test asserts no `@` survives
  anywhere in the answer, in any scope.
- **Attested mailboxes only**, on `sender_roster`'s rule. An account with
  no attestation is unreachable rather than reachable-then-filtered, which
  is what keeps the excluded identities out without naming them.
- **Recency is counted, not assumed.** From queue rows carrying `sent_at`
  inside the window. A queue that refused makes the answer say so; it does
  not read as "no sends".
- **Health per domain is internal only.** Which domains send for a client
  is theirs; how healthy we judge our own infrastructure is ours.

## 3. THE LIST IS BUILT IN CODE

Sixty-nine domains retyped by a language model is sixty-nine chances to
drop a hyphen, and the reader cannot tell a typo from a domain they have
not seen before — which is precisely the confusion that started this. So
the block is assembled from the readback and appended verbatim; the model
writes only the sentence in front of it.

A **domain guard** now sits beside the number guard: any domain-shaped
token in the model's prose that the material does not contain discards the
answer, exactly as an invented figure does.

---

## 4. FOUR DEFECTS THE FIRST DRY RUN SHOWED

Every one of them was invisible until the real question was run through it.

1. **The prose contradicted the list.** The model wrote, in Croatian, "the
   list I can see here is not complete, so I do not want to paste you half
   of it — I will ask the team for a full verified list and put it in this
   thread" — and the full verified list was appended immediately
   underneath. It had no way to know. It is told now, and told the list is
   already grouped with counts, so it stops offering to do that too.
2. **The block was English inside a Croatian answer.** Localised.
3. **Its totals disagreed with itself.** "69 domains" over a list whose
   rows outnumber 69, because a domain can sit under two senders. The
   summary line says DISTINCT and says why.
4. **A recurring guard trip on a rate** the material did carry — fixed
   earlier today by comparing numerically and letting a `*_percent` field
   license the sign.

---

## 5. LANGUAGE, AND SILENCE

**Language.** `src/slacklanguage.py`: two languages, diacritics plus
function words, and it **abstains** when it cannot tell — `None` means
"mirror it" to the model and "English" to the lines written in code.
Detection exists for the two things a prompt cannot do: the lines this
system writes itself, and the log. The real question scores 16–0 Croatian.

**Silence.** The agent answers when mentioned. A question addressed to two
named colleagues is not answered by a bot — answering it would be answering
*for* them. The one way silence breaks is a Resonate person replying
`@Resonate OS answer this` (or `odgovori na ovo`), checked against
`slackscope.internal_users` rather than against the channel: a client
saying "answer this" is a client asking a question.

A relay answers the **parent**, in the parent's language, and opens with
one line saying it is a system readback and not a reply from the colleagues
addressed. **That line names nobody** — an earlier draft named the two
people from the thread it was written against, which would have put their
names on every relayed answer in every channel.

---

## 6. THE CROATIAN DRY RUN

Posted nowhere. Full text is in the session transcript; the opening is:

> Ovo je automatski izvještaj iz sustava, stanje 2026-09-22T11:52:12Z —
> nije odgovor kolega kojima ste se obratili.
>
> Bok, nadam se da ste dobro. Ispod ovog odgovora automatski se nalazi
> cijeli popis domena s kojih se šalju mailovi u vašim email kampanjama,
> grupiran po pošiljatelju, s brojem mailboxova po domeni i oznakom je li
> domena slala u posljednjih 7 dana […]
>
> 69 različitih domena za slanje, ukupno 159 mailboxova.
> Ista domena može biti kod više pošiljatelja.

---

## 7. TESTS

    tests/test_slack_agent_language_and_relay.py            22  NEW
    tests/test_a_client_can_never_reach_another_client.py   43  (+8)

Every slack module passes **alone**. `tests/test_invariants.py` has its one
pre-existing failure (two modules importing `ProviderError` by name), which
is not from this branch.

The scope test the operator asked for: Productive's channel lists
Productive's domains; a second synthetic client's channel cannot see one of
them, cannot reach them through a workspace argument, and cannot see the
sender's name.

---

## 8. INCREMENT 2 — SENDERS, SEATS, AND THE HISTORY

Added at `713d0bf4`, same branch, same rules: nothing merged, nothing
pushed to master.

### 8a. `hr-` vs `li-` is resolved WITHOUT a canonical scheme being chosen

    email     account_id "eb-2736"
    linkedin  account_id "hr-116968"      <- the attestation
    roster    account_id "li-116968", provider_account_id "116968"

**`src/senderownership` writes NEITHER.** `attest()` stores whatever
`account_id` its caller hands it. `li-` comes from code
(`src/senderinventory.py:298`); `hr-` comes from nothing in the tree — it
was written ad hoc, as `scripts/attestation_packet.py` instructs.

So there is no scheme to declare canonical from `senderownership`, and the
operator's fallback applies: **reconciling them is filed here for you**.
Meanwhile the seat count works, by joining on `provider_account_id` — the
bare id both sides carry. That is not a mapping invented here:
`scripts/batch_linkedin_push.py:88` already does
`str(account_id).replace("hr-", "")` and pushes live campaigns on the
result. **32 of 33 seats now resolve.**

### 8b. AND RESOLVING IT IMMEDIATELY EXPOSED SOMETHING

The seat roster mixes two organisations. Alongside the client's staff it
carries **Resonate's own people**, and the register already records "we own
4 of 86" seats in this estate. Nothing in the data says which seat belongs
to whom.

Your rule is that a client channel never names Resonate's own accounts. So
a client channel now names only people with an attested **mailbox** — the
eight who match the handoff's estate — and LinkedIn seats are given as a
workspace total with a note saying they are not attributed. Internal scope
is unchanged. Verified: client 8 named, 0 Resonate people; internal 40.

**Seat ownership is a decision for you.** Until it is made, no client
channel names a seat holder.

### 8c. The history, and what reading it found

6,091 messages, 22 channels. All seven scopes verified by real reads;
`channels:join` proved by joining three public rooms. Nine externally
shared channels skipped and listed; thirteen private ones the bot was
already in.

`docs/SLACK-AGENT-QUESTION-CATALOGUE.md` and
`docs/SLACK-AGENT-EXPECTATIONS.md` carry the output. Both were scanned for
addresses, client names, person names and phone numbers before commit and
are clean.

**Two things you should see:**

- **A credential is in Slack history in plain text** (a GoDaddy password),
  along with payroll and personal phone numbers. It is now also in
  `work/slack-history/`, which is gitignored and uncommitted. The mining
  skips those rooms and drops credential-shaped messages whole, but the
  password in Slack is a standing exposure that predates any of this.
- **A client asked, in their own channel, "can you please stop sending
  messages to people who have replied????"** — four question marks. That is
  a reply-stop complaint and the highest-severity shape in the corpus. The
  agent would raise a `stop_account` ticket, which is right and is not
  enough; a question of that shape should reach you immediately.

### 8d. Still yours

- Reconcile `hr-`/`li-` properly.
- Decide seat ownership, or accept counts-without-names indefinitely.
- Decide the eight unbound shared client channels: bind, leave, or
  authorise reading.
- `src/providers/slack.py` `thread_parent` — unchanged, still for review.
