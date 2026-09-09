# Production authentication

How somebody proves who they are, why it is an identity provider and not a
password, and exactly what has to be created before a deployment can hold
real client data.

Read `RELEASE-CANDIDATE.md` §7 first if you want the verdicts. This
document is the mechanism.

---

## 1. The two questions, and why they stay apart

**Authentication** answers *who is this person*. An identity provider does
it. This system never sees a password, stores no credential, and runs no
reset flow.

**Authorisation** answers *what may they do*. `workspaces.jsonl` does it -
the user row, the membership, the role - resolved on the server on every
single request.

Nothing about the second comes from the first. A provider that is
perfectly happy about somebody says nothing at all about whether they work
here, and the tests that matter most in `tests/test_production_auth.py`
are the ones where the provider says yes and this system still says no.

This split is not new. It is why `Sessions.create` has always stored *who*
and never *what they may do*, and why `security.membership()` re-resolves
the role per request. What was missing was only the first half.

---

## 2. Why an identity provider

Three reasons, in the order they mattered.

**We would be inventing password security.** Storage, hashing parameters,
reset flows, rate limiting, breach response. Every one of those is
something somebody else already does better and something this repository
would then own for ever.

**There is nowhere to send an email from.** A magic link or an OTP needs a
transport, and the central safety property of this build is that it cannot
send: `push.run(live=True)` raises, `tagsync.send` refuses. Adding an
outbound mail path so people can log in would put a sending capability
into the one system designed not to have one.

**The people who need accounts already have accounts.** Resonate operators
and the agency's clients are on Google Workspace or Microsoft 365. The
identity exists; only the proof was missing.

### And why it has no dependencies

`DEPLOYMENT-PLAN.md` §1 calls zero third-party dependencies the
deployment's biggest advantage, and `tests/test_deployment_config.py`
asserts it against every import in `src/`. An OIDC client needs a
redirect, a form POST and some comparisons - `urllib` does the first two
and `hmac.compare_digest` does the third. An SDK here would trade a proven
property for code we would still have to read.

---

## 3. The flow

```
  /login          one button. No user list, no form, no addresses.
       │
  /auth/start     mint state, nonce and a PKCE verifier
       │          remember them server-side, single use
       ▼
  the provider    authenticates however it likes: password, passkey,
       │          hardware key, SSO. None of it reaches this process.
       ▼
  /auth/callback  state must be one we minted and have not used
       │          exchange the code at the token endpoint, over TLS
       │          check iss, aud, exp, nonce, email_verified, domain
       ▼
  _establish      the proved address, looked up in workspaces.jsonl.
                  No row, or no membership -> 403 and no session.
```

Both mechanisms end at `_establish`, which is the only place in the
application that creates a session. Whatever proved the address, what
happens next is resolved the same way from the same table.

| guard | what it stops |
| --- | --- |
| `state`, single use, server-side, constant-time | somebody else's callback replayed into your browser |
| `nonce`, echoed in the id_token | a token minted for a different request |
| PKCE `S256` | an intercepted authorization code redeemed by anyone else |
| `iss`, `aud` | a token from another provider, or for another client |
| `exp` | an expired token |
| `email_verified` | an address the provider has not itself confirmed |
| `AUTH_ALLOWED_DOMAINS` | a valid account from outside the organisation |
| the roster | anybody at all who is not already a user here |
| TLS on every endpoint | reading the client secret, or the code, off the wire |

### The one deliberate simplification

**The id_token's signature is not verified**, and that is allowed for a
specific reason: this client only ever reads an id_token that came back in
the body of its own POST to the provider's token endpoint, over TLS,
authenticated with the client secret. OpenID Connect Core §3.1.3.7 permits
skipping signature validation when the token is obtained through exactly
that channel, because TLS has already proved who sent it.

The alternative is RSA and JWKS in the standard library - a signature
verifier we would be writing ourselves, and one with a bug in it is worse
than one we correctly did not need.

**The precondition is enforced, not assumed.** `oidc.require_tls()`
refuses any non-loopback endpoint that is not `https`, and two mutations in
`tools/mutation_audit.py` exist to stop that check being removed. Loopback
is exempt so the tests can stand up a real provider on an ephemeral port.

### Validated against Google's real document

The discovery leg is not a fixture. `https://accounts.google.com/.well-known/openid-configuration`
is public and unauthenticated, so it was read directly - no secret, no
credit, no write - and every assumption this client makes was confirmed:

| | |
| --- | --- |
| issuer | matches what we configure |
| authorization endpoint | `https://accounts.google.com/o/oauth2/v2/auth` |
| **token endpoint** | **`https://oauth2.googleapis.com/token` - a different host** |
| PKCE `S256` | supported |
| `code` flow | supported |
| `openid`, `email` | both advertised |
| `iss` `aud` `exp` `sub` `email` `email_verified` | all advertised |

**The different host is the finding.** Google exchanges tokens somewhere
other than where it issues them, which is ordinary and is exactly why the
endpoints are discovered rather than derived. The fake provider in the
tests serves both from one port, so it could never have caught a client
that quietly built the token URL from the issuer - and a client that did
would work against every test here and fail on first contact with Google.
`TheTokenEndpointIsWhereverDiscoverySaysItIs` covers it now, and a
mutation puts the bug back to prove it bites.

---

## 4. What decides which mechanism is running

`AUTH_PROVIDER`, and nothing else. Not `APP_MODE`, not which interface is
bound, not anything on a request.

| `AUTH_PROVIDER` | what happens |
| --- | --- |
| unset | demo sign-in: pick an email from a list. No password |
| `oidc` | the identity provider, if all four settings are present |
| `oidc`, partly configured | **refused**, naming what is missing |
| anything else | **refused**, naming the value |

That last row is the one worth dwelling on. `okta` is a plausible thing to
type. Falling back to demo sign-in because of it would be unauthenticated
access reached by way of a variable somebody set in order to turn
authentication *on* - so it raises rather than shrugging.

Setting `AUTH_PROVIDER=oidc` is also what lets the process run with
`APP_MODE=production` and bind a reachable interface at all. Both refusals
in `web.app.check_configuration` read one predicate,
`security.sign_in_proves_identity()`, so they lift together and cannot
drift apart.

---

## 5. What you have to create

**This is the boundary this repository cannot cross on its own.** An OAuth
client is an account action, and the values it produces are secrets.

### Google Workspace

1. Google Cloud Console → your project → **APIs & Services** →
   **Credentials**.
2. **Create Credentials** → **OAuth client ID** → Application type **Web
   application**. Name it something recognisable, e.g. `Resonate Control
   Center`.
3. Under **Authorised redirect URIs**, add exactly:
   `https://<your app host>/auth/callback`
   It must match `AUTH_REDIRECT_URL` character for character, and it must
   be `https`.
4. Create. Copy the **Client ID** and **Client secret**.
5. On the OAuth consent screen, set **User type: Internal** if everyone who
   signs in is in your Workspace. That is a second fence and it costs
   nothing.

**Scopes: `openid` and `email`. Nothing else.** Every claim this system
reads comes from those two - `openid` carries `iss`, `aud`, `exp`, `nonce`
and `sub`; `email` carries `email` and `email_verified`. `profile` was
requested briefly and never read, so it was removed: a consent screen is a
promise to a person, and asking for a name this system never looks at is a
claim about ourselves that is not true.
`test_it_asks_for_no_scope_it_does_not_read` fails if that drifts.

**Authorised JavaScript origins: leave empty.** The flow is a server-side
redirect and a server-to-server token exchange. Nothing runs in the
browser, and an origin listed here would be permission nothing uses.

Then set, in the platform's secret store and nowhere else:

```
AUTH_PROVIDER=oidc
AUTH_ISSUER=https://accounts.google.com
AUTH_CLIENT_ID=<the client id>
AUTH_CLIENT_SECRET=<the client secret>
AUTH_REDIRECT_URL=https://<your app host>/auth/callback
AUTH_ALLOWED_DOMAINS=resonategroup.co
```

### Microsoft Entra ID

The same shape. Register an application, add the redirect URI as a **Web**
platform, create a client secret, and use
`https://login.microsoftonline.com/<tenant id>/v2.0` as `AUTH_ISSUER`.

### Before anybody can sign in

**Every person needs a user row already.** No account is created by
signing in: `workspaces.jsonl` is the canonical roster, and a directory
that can add people to it is a directory that decides who works here. A
proved address with no row gets 403 and a page telling them to ask an
administrator - and that page names nobody who does have access.

---

## 5b. Giving somebody access before they have ever signed in

`assign` refuses to write a membership for an address with no user row,
and its reason is right: *a membership pointing at nobody grants a
permission to whoever registers that address next.* So Settings → Users
answered "no such user" for everybody who mattered - the people who did
not have an account yet - and the only route in was to make somebody sign
in, be turned away, and try again.

An **invitation** is the missing state, and it is a different kind of row
in `workspaces.jsonl`:

| | |
| --- | --- |
| grants | nothing |
| visible to `membership_of` | no |
| visible to any permission check | no |
| read by | `/auth/callback`, and only after the identity proof |

It is a standing instruction: *if an identity provider ever proves this
exact address, give it this role in this workspace.*

### What consumes it, and what cannot

| | |
| --- | --- |
| The exact normalised address | `tina@example.test` — not `tina+w@example.test`, not `anyone-else@example.test`, not a prefix |
| Only the workspace it names | an invitation to one says nothing about any other |
| The role an administrator chose | written before the person appeared; nothing on the request decides it |
| Only a **proved** address | `_establish` takes an explicit `proved` flag that only `/auth/callback` sets |

That last row is the one to keep. The flag is passed explicitly rather
than inferred from the provider's `subject`, which a provider is allowed
to omit — and inferring it would mean the demo sign-in could claim an
invitation by having an address typed into a form, which is precisely what
invitations exist not to be.

### Roles

`assignable_roles()` is `ROLES` minus `SUPER_ADMIN`. Super admin is an
account-level fact on the user row, and nothing reachable from inside a
workspace grants it — the form refuses it, `invite` refuses it, and the
dropdown never offers it.

The endpoint requires `users.manage`, and the target workspace is
`repo.workspace`, resolved from the session. A workspace named in the form
decides nothing.

### Revocation

Immediate, and the only control there is. **No expiry**: an offer that
grants nothing until Google proves the address is not a credential lying
around, and an expiry would be a background job plus a second thing to get
wrong. A revoked invitation is marked rather than deleted, because "this
was offered and taken back" is a different fact from "this never
happened".

---

## 6. What is still true afterwards

- **Sessions live in memory.** A restart signs everybody out.
  `PRODUCT-GAPS.md` §6. Correct for one process; it becomes wrong the
  moment there is a second, which is the same trigger as the database
  migration.
- **`SESSION_SECRET` is read by nothing.** It was `REQUIRED` in production
  while production authentication did not exist, which made it a required
  variable nothing consumed - the thing an operator sets to clear an error,
  where clearing it changes nothing. It is now `OPTIONAL` and reserved for
  the session store a second process would need. Five variables that gate a
  real provider replaced one that gated nothing.
- **Nothing sends.** Authentication changes who may look at the system. It
  does not change what the system may do, and `push.run(live=True)` still
  raises.
- **The demonstration is unaffected.** With `AUTH_PROVIDER` unset the demo
  sign-in is exactly what it was, which is what keeps the published
  fictional estate working.
