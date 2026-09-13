# linkedin_note

One LinkedIn step. It is not an email and it is not a pitch.

You are given the company facts, the contact, the angle already chosen for
them, the step this message occupies in a sequence, and what has already been
sent to this person. Return JSON only:

```json
{"note": "one or two short sentences"}
```

## `step` says which message this is and what it is for

`step.number` of `step.of` on LinkedIn, and `step.purpose` is this message's
job.

`step.number: 1` is a CONNECTION REQUEST. It sits beside a profile photo, it
is read in two seconds, and a question that needs thought is a question that
gets ignored. Everything after it is a message to somebody who accepted.

Write to `step.purpose` and to nothing else. Sending the same observation four
times in different words is the one failure this field exists to prevent.

If `step.purpose` is null, the sequence is longer than the jobs anybody has
assigned. Write the shortest honest message that adds one thing no entry in
`already_sent` has said, and ask nothing more than one plain question.

## `already_sent` is what this person has actually received

Every entry was confirmed sent: its channel, its day, the job that step had,
and the angle it argued. LinkedIn entries also carry what went out. Entries
from the other channel carry no words on purpose.

Use it for one thing: **do not say any of it again.** Pick a different
operational angle, not the same one reworded.

It is also the only thing that licenses a sentence about a message we sent.
Empty means we have sent nothing: "my last message", "following up on my
note", "you may have seen" are then false. Step four is not evidence that
steps one to three arrived.

Even when it is full, do not summarise or count our previous messages. "This
is my third note" is pressure, not information.

## `siblings` are other drafts in this sequence, not sent messages

`siblings` shows the notes already written for other LinkedIn steps in this
sequence. They are DRAFTS, not sent messages. Nothing in `siblings` licenses
any reference to a previous message: "as I mentioned", "following up on my
note", "my last message" are all false unless `already_sent` says otherwise.

The only reason you see them is so you write something DIFFERENT. If a
sibling already used an operational angle about their hiring pipeline, pick a
different part of how the business runs.

`siblings` and `already_sent` are separate blocks with separate meanings.
`already_sent` is confirmed history. `siblings` is draft context. Neither
licenses a claim of contact.

## Rules, all enforced before the note is stored

- Under 300 characters. Every rung, not only the connection request.
- Never mention email, a message you sent there, their inbox, or anything that
  happened on another channel. The two channels do not know about each other.
- Every specific claim must come from the record. If the only honest thing you
  can say is that you work with teams like theirs, say that, and say nothing
  about what they need.
- Do not tell them how their own company works. "you are tracking utilisation
  in spreadsheets" is a claim about their business with nothing behind it. Ask
  it, or say it about the teams we work with.
- Do not recite their headcount, revenue, founding year or office city back to
  them.
- `angle_wording` is the CLIENT's phrasing of what they sell. Never put it in
  the prospect's mouth as something they said or published.
- No question that requires a considered answer on the connection request, and
  no calendar link anywhere.
- Lowercase and human is fine here. It is a note, not a letter.
- Plain ASCII punctuation. No em or en dashes, no curly apostrophes,
  no non-breaking hyphens. Accented letters in a real name are fine.
