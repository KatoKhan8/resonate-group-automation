"""Offline material batch capture; sibling code is trusted local package code.
No transport, credentials, grants, production state, or authenticated evidence.
"""
import hashlib
import types
from pathlib import Path

_path = Path(__file__).with_name('bounded_pages.PROPOSED.py')
_raw = _path.read_bytes()
if hashlib.sha256(_raw).hexdigest() != 'c1760e58473a515016427848dedd960612b687a38e03e130eaf615ec84dd7c37':
    raise ValueError('material page dependency drift')
_pages = types.ModuleType('pinned_material_page_decoder')
_pages.__file__ = str(_path)
exec(compile(_raw, str(_path), 'exec'), _pages.__dict__)
Refused = _pages.AcquisitionRefused


class MaterialCapture:
    """Terminal ordered decoder, not a worker or a full namespace snapshot."""
    def __init__(self, lead_ids, started_at):
        if (type(lead_ids) is not list or len(lead_ids) != 4
                or any(type(x) is not int or not 0 < x <= 9007199254740991 for x in lead_ids)
                or len(set(lead_ids)) != 4 or type(started_at) is not int or started_at < 0):
            raise Refused('material input binding')
        self.routes = tuple('/leads/' + str(x) for x in lead_ids) + (
            '/campaigns/540', '/campaigns/540/leads',
            '/campaigns/v1.1/540/sequence-steps',
            '/campaigns/540/sender-emails', '/custom-variables')
        self.started = self.last_time = started_at
        self.stage = self.attempts = self.bytes_seen = 0
        self.failed = self.closed = False
        self.components = []
        self.receipts = []
        self.collection = None
        self.lead_ids = tuple(lead_ids)

    def feed(self, frame):
        if self.failed or self.closed:
            raise Refused('material capture terminal')
        try:
            if type(frame) is not dict or set(frame) != {'raw','route','http_status','workspace_id','observed_at','page'}:
                raise Refused('material frame schema')
            raw, now = frame['raw'], frame['observed_at']
            if (type(raw) is not bytes or not raw or len(raw) > 1048576
                    or type(now) is not int or now < self.last_time or now - self.started > 600
                    or self.attempts >= 32 or self.bytes_seen + len(raw) > 8388608
                    or self.stage >= len(self.routes) or frame['route'] != self.routes[self.stage]):
                raise Refused('material frame bounds or order')
            self.last_time = now
            self.attempts += 1
            self.bytes_seen += len(raw)
            route = self.routes[self.stage]
            if self.stage in (5,7,8):
                if self.collection is None:
                    self.collection = _pages.PageAssembly(10, now, endpoint=route)
                owner = self.collection
                owner.feed(raw, page=frame['page'], workspace_id=frame['workspace_id'],
                           observed_at=now, http_status=frame['http_status'], endpoint=route)
                if len(owner.receipts) == owner.metadata[1]:
                    result = owner.finish(workspace_id=frame['workspace_id'], observed_at=now,
                                          unique_field='name' if route == '/custom-variables' else 'id')
                    self.components.append(dict(route=route, observation=result))
                    self.collection = None
                    self.stage += 1
            else:
                if frame['page'] is not None:
                    raise Refused('unexpected material page')
                result = _pages.decode_single_response(raw, route=route,
                    http_status=frame['http_status'], workspace_id=frame['workspace_id'],
                    lead_id=self.lead_ids[self.stage] if self.stage < 4 else None)
                self.components.append(dict(route=route, observation=result))
                self.stage += 1
            self.receipts.append(dict(route=route, http_status=frame['http_status'],
                workspace_id=frame['workspace_id'], observed_at=now, page=frame['page'],
                response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw)))
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        if self.failed or self.closed:
            raise Refused('material capture terminal')
        self.closed = True
        if self.stage != len(self.routes) or self.collection is not None:
            self.failed = True
            raise Refused('incomplete material frames')
        # Detached output; no complete namespace snapshot or inferred nonuse.
        import copy
        return dict(schema='offline-material-capture/1', components=copy.deepcopy(self.components),
            attempts=self.attempts, response_bytes=self.bytes_seen,
            receipts=copy.deepcopy(self.receipts), workspace_binding='CALLER_SUPPLIED_ASSERTIONS_ONLY',
            workspace_bookends_verified=False,
            started_at=self.started, finished_at=self.last_time,
            producer_authenticated=False, freshness_proven=False, snapshot_ready=False,
            readiness=False, send_allowed=False, write_allowed=False,
            missing_authority=['canonical_identity_binding','namespace_nonuse',
                'sequence_title_if_absent','native_step_material_validation','receipt_provenance'])
