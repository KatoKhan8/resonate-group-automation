# linkedin_note

A LinkedIn connection request note. It is not an email and it is not a pitch.

You are given the company facts, the contact, and the angle already chosen for
them. Return JSON only:

```json
{"note": "one or two short sentences"}
```

Rules, all enforced before the note is stored:

- Under 300 characters. A connection request is not a paragraph.
- Never mention email, a message you sent, their inbox, or anything that
  happened on another channel. The two channels do not know about each other.
- Every specific claim must come from the record. If the only honest thing you
  can say is that you work with teams like theirs, say that, and say nothing
  about what they need.
- No question that requires a considered answer, and no calendar link.
- Lowercase and human is fine here. It is a note, not a letter.
