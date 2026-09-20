"""A stateful EmailBison, standing in for the real one at the transport.

WHY A STATEFUL FAKE AND NOT A SCRIPT OF RESPONSES. Everything this file exists
to prove is about ORDER and about WHAT IS ALREADY THERE: whether a second run
creates a second campaign, whether a lead is attachable while another campaign
holds it, whether a pause happened before the leads did. A canned response per
route cannot answer any of those, because none of them is a property of one
call.

EVERY BEHAVIOUR MODELLED HERE WAS MEASURED AGAINST THE LIVE PROVIDER ON
2026-09-13, and each is annotated with what was observed. That is the only
thing that makes a fake worth testing against - a fake built from what the
docs imply proves that the code agrees with a guess.
"""
import json
import urllib.parse


class FakeBison:
    """One workspace, with campaigns, leads and their memberships."""

    #: A lead in a campaign that has not been stopped reads `in_sequence`
    #: IMMEDIATELY - draft is enough, the campaign does not have to be running.
    #: Pausing the campaign moves it to `sending_paused`.
    IN_SEQUENCE = "in_sequence"
    PAUSED_MEMBER = "sending_paused"

    def __init__(self, workspace=10, name="PRODUCTIVE"):
        self.workspace = {"id": workspace, "name": name}
        self.campaigns = {}
        self.leads = {}
        self.schedules = {}
        self.senders = {}
        self.sequences = {}
        self.members = {}          # campaign id -> [lead id]
        self.variables = set()
        self.calls = []            # (method, path) in order, for order proofs
        self.attach_states = []    # campaign status at each attach-leads
        self.stopped = {}          # campaign id -> leads told to stop
        self.queue = {}            # campaign id -> pre-send rows
        self.sending_schedule = {} # campaign id -> {day -> emails_being_sent}
        self._next_campaign = 500
        self._next_lead = 900
        self._next_step = 4000
        #: Set to a status to make the next resume land there.
        self.resume_lands_on = "active"
        #: Seconds of index lag on /leads?search=, in calls rather than time.
        self.search_lag_calls = 0
        self._searches = {}

    # ------------------------------------------------------------- helpers
    def add_campaign(self, name, status="draft"):
        self._next_campaign += 1
        ident = self._next_campaign
        self.campaigns[ident] = {
            "id": ident, "name": name, "status": status,
            "max_emails_per_day": 1000, "max_new_leads_per_day": 1000}
        self.members[ident] = []
        return ident

    def add_lead(self, email, **fields):
        self._next_lead += 1
        ident = self._next_lead
        row = {"id": ident, "email": email, "custom_variables": []}
        row.update(fields)
        self.leads[ident] = row
        return ident

    def member_status(self, campaign_id, lead_id):
        # A deleted campaign leaves no membership behind, so a lead that was
        # in it is in nothing. Modelled because the rebuild case reaches it.
        if campaign_id not in self.campaigns:
            return None
        if lead_id not in self.members.get(campaign_id, []):
            return None
        if int(lead_id) in self.stopped.get(campaign_id, set()):
            return "stopped"
        status = str(self.campaigns[campaign_id].get("status") or "").lower()
        return self.PAUSED_MEMBER if status == "paused" else self.IN_SEQUENCE

    def held_elsewhere(self, lead_id, campaign_id):
        return [c for c, ids in self.members.items()
                if c != campaign_id and lead_id in ids
                and self.member_status(c, lead_id) == self.IN_SEQUENCE]

    def _campaign_data(self, lead_id):
        return [{"campaign_id": c, "status": self.member_status(c, lead_id)}
                for c, ids in self.members.items()
                if lead_id in ids and c in self.campaigns]

    # ------------------------------------------------------------- transport
    def __call__(self, method, url, headers=None, body=None, timeout=None):
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path
        for prefix in ("/api", ""):
            if prefix and path.startswith(prefix):
                path = path[len(prefix):]
                break
        params = dict(urllib.parse.parse_qsl(parsed.query))
        if isinstance(body, (bytes, str)):
            body = json.loads(body)
        self.calls.append((method, path))
        return self.route(method, path, params, body or {})

    def route(self, method, path, params, body):
        parts = [p for p in path.split("/") if p]
        if path == "/users":
            return 200, {"data": {"workspace": dict(self.workspace)}}
        if path == "/custom-variables":
            if method == "GET":
                # Fifteen a page here too, which is one variable away from
                # mattering: this workspace has twelve declared.
                return self._page([{"name": n, "id": i} for i, n
                                   in enumerate(sorted(self.variables))],
                                  params)
            self.variables.add(body.get("name"))
            return 201, {"data": {"name": body.get("name")}}
        if path == "/campaigns" and method == "GET":
            return self._list_campaigns(params)
        if path == "/campaigns" and method == "POST":
            ident = self.add_campaign(body.get("name"))
            return 201, {"data": dict(self.campaigns[ident])}
        if path == "/leads" and method == "GET":
            return self._search_leads(params)
        if path == "/leads" and method == "POST":
            return self._create_lead(body)
        if parts[:1] == ["leads"] and len(parts) == 2:
            return self._one_lead(method, int(parts[1]), body)
        if parts[:1] == ["campaigns"] and len(parts) >= 2:
            return self._campaign_route(method, parts, params, body)
        return 404, {"data": {"success": False, "message": f"no route {path}"}}

    #: What a campaign's lead list and sender list actually serve, whatever
    #: `per_page` asks for. Measured on campaign 352: `per_page=200` answers
    #: fifteen rows with `meta.per_page: 15`, `meta.total: 21159`,
    #: `meta.last_page: 1411`. Modelled here because every read that trusted
    #: `per_page` was silently returning a page as a membership.
    SERVED_PER_PAGE = 15

    def _page(self, rows, params):
        """One page of a route that IGNORES `per_page`."""
        page = int(params.get("page") or 1)
        size = self.SERVED_PER_PAGE
        pages = max(1, -(-len(rows) // size))
        return 200, {"data": rows[(page - 1) * size:page * size],
                     "meta": {"current_page": page, "last_page": pages,
                              "per_page": size, "total": len(rows)}}

    # ------------------------------------------------------------- campaigns
    def _list_campaigns(self, params):
        rows = [dict(c) for c in self.campaigns.values()]
        per_page = int(params.get("per_page") or 15)
        page = int(params.get("page") or 1)
        pages = max(1, -(-len(rows) // per_page))
        chunk = rows[(page - 1) * per_page:page * per_page]
        return 200, {"data": chunk,
                     "meta": {"current_page": page, "last_page": pages,
                              "per_page": per_page, "total": len(rows)}}

    def _campaign_route(self, method, parts, params, body):
        ident = int(parts[1])
        if ident not in self.campaigns:
            return 404, {"data": {"success": False, "message": "Record not found."}}
        tail = parts[2:]
        campaign = self.campaigns[ident]
        if not tail and method == "GET":
            return 200, {"data": dict(campaign)}
        if tail == ["update"] and method == "PATCH":
            campaign["name"] = body.get("name", campaign["name"])
            campaign["max_emails_per_day"] = body.get("max_emails_per_day")
            campaign["max_new_leads_per_day"] = body.get("max_new_leads_per_day")
            return 200, {"data": dict(campaign)}
        if tail == ["schedule"]:
            return self._schedule(method, ident, body)
        if tail == ["sender-emails"] and method == "GET":
            return self._page([{"id": s} for s in self.senders.get(ident, [])],
                              params)
        if tail == ["attach-sender-emails"] and method == "POST":
            self.senders.setdefault(ident, [])
            for s in body.get("sender_email_ids") or []:
                if s not in self.senders[ident]:
                    self.senders[ident].append(s)
            # Answers 200 with success:false even when it attached nothing.
            return 200, {"data": {"success": False}}
        if tail == ["sequence-steps"] and method == "GET":
            held = self.sequences.get(ident)
            if not held:
                # 200 WITH success:false, exactly like the schedule route.
                return 200, {"data": {"success": False, "message":
                                      "Sequence steps do not exist"}}
            # NOT paginated: campaign 352 returns all 44 steps in one
            # response with no `meta`, and `?page=2` returns the same 44.
            return 200, {"data": [dict(s) for s in held]}
        if tail == ["sequence-steps"] and method == "POST":
            # IT APPENDS. Two writes leave two steps; there is no replace and
            # no delete, and the provider renumbers `order` across the writes.
            held = self.sequences.setdefault(ident, [])
            for step in body.get("sequence_steps") or []:
                self._next_step += 1
                held.append({"id": self._next_step, "active": True,
                             "order": len(held) + 1,
                             "email_subject": step.get("email_subject"),
                             "email_body": step.get("email_body"),
                             "wait_in_days": step.get("wait_in_days"),
                             "variant": step.get("variant", False),
                             "variant_from_step": step.get(
                                 "variant_from_step"),
                             "thread_reply": step.get("thread_reply")})
            return 201, {"data": {"id": ident}}
        if tail == ["leads"] and method == "GET":
            return self._page([
                {"id": lid, "email": self.leads[lid]["email"],
                 "lead_campaign_data": self._campaign_data(lid)}
                for lid in self.members.get(ident, [])], params)
        if tail == ["leads", "attach-leads"] and method == "POST":
            return self._attach(ident, body.get("lead_ids") or [])
        if tail == ["leads", "stop-future-emails"] and method == "POST":
            # Answers 200 for a lead it does not hold, and does nothing.
            for lead_id in body.get("lead_ids") or []:
                if lead_id in self.members.get(ident, []):
                    self.stopped.setdefault(ident, set()).add(int(lead_id))
            return 200, {"data": {"success": True}}
        if tail == ["leads"] and method == "DELETE":
            for lead_id in body.get("lead_ids") or []:
                if lead_id in self.members.get(ident, []):
                    self.members[ident].remove(lead_id)
            return 200, {"data": {"success": True}}
        if tail == ["pause"] and method == "PATCH":
            campaign["status"] = "paused"
            return 200, {"data": dict(campaign)}
        if tail == ["resume"] and method == "PATCH":
            campaign["status"] = self.resume_lands_on
            return 200, {"data": dict(campaign)}
        if tail == ["scheduled-emails"] and method == "GET":
            return self._page(self.queue.get(ident, []), params)
        if tail == ["sending-schedule"] and method == "GET":
            return self._sending_schedule(ident, params)
        return 404, {"data": {"success": False, "message": "no route"}}

    def _schedule(self, method, ident, body):
        existing = self.schedules.get(ident)
        if method == "GET":
            if not existing:
                # 200 WITH success:false. Absence is in the body, not the code.
                return 200, {"data": {"success": False,
                                      "message": "Schedule does not exist"}}
            return 200, {"data": dict(existing)}
        if method == "POST":
            if existing:
                # MEASURED: POST will not replace. 200, and it writes nothing.
                return 200, {"data": {"success": False,
                                      "message": "Schedule already exists"}}
            self.schedules[ident] = self._stored(body)
            return 201, {"data": dict(self.schedules[ident])}
        if method == "PUT":
            self.schedules[ident] = self._stored(body)
            return 200, {"data": dict(self.schedules[ident])}
        return 405, {"message": "Supported methods: GET, HEAD, POST, PUT."}

    @staticmethod
    def _stored(body):
        row = {k: bool(v) for k, v in body.items() if isinstance(v, bool)}
        # A time written as "09:00" reads back as "09:00:00".
        for field in ("start_time", "end_time"):
            value = str(body.get(field) or "")
            row[field] = value if value.count(":") == 2 else value + ":00"
        row["timezone"] = body.get("timezone")
        row["id"] = 1
        return row

    def _sending_schedule(self, campaign_id, params):
        """The provider's answer to 'what will actually send' on a given day.

        Returns 400 with "No emails scheduled for this period" when the
        campaign has nothing planned for the requested day - the provider's
        ordinary empty answer, not an error. A test pins this apart from a
        transport failure and from a zero count.
        """
        day = params.get("day", "")
        held = self.sending_schedule.get(campaign_id, {})
        count = held.get(day)
        if count is None:
            # THE 400 IS THE EMPTY ANSWER. Measured 2026-09-20 against both
            # live campaigns, all three days: HTTP 400 with this exact message.
            return 400, {"data": {"success": False,
                                  "message": "No emails scheduled for this period"}}
        return 200, {"data": {"emails_being_sent": count, "day": day}}

    def _attach(self, ident, lead_ids):
        # What the campaign's status WAS at the moment somebody was put into
        # it. Anything but `paused` means these leads read `in_sequence` from
        # here on, and are unattachable to any other campaign until this one
        # is stopped - so this is the invariant, not the call order.
        self.attach_states.append(self.campaigns[ident].get("status"))
        blocked = [i for i in lead_ids if self.held_elsewhere(i, ident)]
        if blocked:
            # ONE SENTENCE FOR THREE FACTS, naming no lead and no campaign,
            # and it attaches NOBODY - not even the leads that were fine.
            return 422, {"data": {"success": False, "message": (
                "No leads were added because they are either in other "
                "sequences, have previously bounced, or unsubscribed")}}
        for i in lead_ids:
            if i not in self.members.setdefault(ident, []):
                self.members[ident].append(i)
        return 200, {"data": {"success": True}}

    # ----------------------------------------------------------------- leads
    def _create_lead(self, body):
        address = str(body.get("email") or "").strip().lower()
        for row in self.leads.values():
            if str(row.get("email") or "").lower() == address:
                return 422, {"data": {"success": False, "message":
                                      "The email has already been taken."}}
        ident = self.add_lead(address,
                              first_name=body.get("first_name"),
                              last_name=body.get("last_name"),
                              custom_variables=list(
                                  body.get("custom_variables") or []))
        return 201, {"data": dict(self.leads[ident])}

    def _search_leads(self, params):
        term = str(params.get("search") or "").strip().lower()
        # THE INDEX LAGS CREATION. Modelled as a number of reads rather than
        # as a wall-clock delay so a test can be deterministic about it.
        self._searches[term] = self._searches.get(term, 0) + 1
        if self._searches[term] <= self.search_lag_calls:
            return 200, {"data": []}
        rows = [dict(r, lead_campaign_data=self._campaign_data(r["id"]))
                for r in self.leads.values()
                if term and term in str(r.get("email") or "").lower()]
        return 200, {"data": rows}

    def _one_lead(self, method, lead_id, body):
        row = self.leads.get(lead_id)
        if row is None:
            return 404, {"data": {"success": False, "message": "Record not found."}}
        if method == "PATCH":
            held = {v["name"]: v for v in row.get("custom_variables") or []}
            for wanted in body.get("custom_variables") or []:
                held[wanted["name"]] = wanted      # PATCH merges, never replaces
            row["custom_variables"] = list(held.values())
        return 200, {"data": dict(row, lead_campaign_data=self._campaign_data(lead_id))}
