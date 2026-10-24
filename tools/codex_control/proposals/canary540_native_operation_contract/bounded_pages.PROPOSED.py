"""Offline, lossless page assembly. No transport, credentials or authority grant."""
import hashlib
import json
import math


class AcquisitionRefused(ValueError):
    pass


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise AcquisitionRefused('nonfinite JSON number')
    return result


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AcquisitionRefused('duplicate JSON key')
        result[key] = value
    return result


class PageAssembly:
    """Consume ordered response bytes from one future bounded read phase.

    Identity/freshness here are supplied observations, never authenticated facts.
    All rows remain intact, including null values and duplicate variable rows.
    A future worker must own transport, receipt authenticity and exclusive grant.
    """
    def __init__(self, workspace_id, started_at, *, max_pages=8,
                 max_rows=102, max_bytes=1048576, max_seconds=60,
                 endpoint="/custom-variables"):
        limits = (workspace_id, started_at, max_pages, max_rows, max_bytes, max_seconds)
        if any(type(x) is not int for x in limits):
            raise AcquisitionRefused('integer limits required')
        if (workspace_id != 10 or started_at < 0 or not 1 <= max_pages <= 8
                or not 1 <= max_rows <= 102 or not 1 <= max_bytes <= 1048576
                or not 1 <= max_seconds <= 60):
            raise AcquisitionRefused('bounded scope required')
        if endpoint not in ("/custom-variables", "/campaigns/540/sender-emails", "/campaigns/540/leads"):
            raise AcquisitionRefused("endpoint outside scope")
        self.endpoint = endpoint
        self.workspace = workspace_id
        self.started = self.last_time = started_at
        self.limits = (max_pages, max_rows, max_bytes, max_seconds)
        self.rows, self.receipts = [], []
        self.metadata = None
        self.bytes_seen = 0
        self.failed = self.closed = False

    def _time(self, observed_at):
        if (type(observed_at) is not int or observed_at < self.last_time
                or observed_at - self.started > self.limits[3]):
            raise AcquisitionRefused('observation time boundary')
        self.last_time = observed_at

    def feed(self, raw, *, page, workspace_id, observed_at, http_status, endpoint):
        if self.failed or self.closed:
            raise AcquisitionRefused('assembly terminal')
        try:
            self._time(observed_at)
            if type(http_status) is not int or not 200 <= http_status < 300 or endpoint != self.endpoint:
                raise AcquisitionRefused("HTTP or endpoint boundary")
            if type(workspace_id) is not int or workspace_id != self.workspace:
                raise AcquisitionRefused('workspace drift')
            if type(page) is not int or page != len(self.receipts) + 1:
                raise AcquisitionRefused('page order')
            if type(raw) is not bytes or not raw or len(raw) + self.bytes_seen > self.limits[2]:
                raise AcquisitionRefused('response byte bound')
            self.bytes_seen += len(raw)
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_float=_float,
                               parse_constant=lambda _: (_ for _ in ()).throw(AcquisitionRefused('nonfinite JSON')))
            if type(value) is not dict or type(value.get('data')) is not list or type(value.get('meta')) is not dict:
                raise AcquisitionRefused('collection envelope')
            meta, rows = value['meta'], value['data']
            for envelope in (value, meta):
                if 'workspace_id' in envelope and (type(envelope['workspace_id']) is not int or envelope['workspace_id'] != self.workspace):
                    raise AcquisitionRefused('envelope workspace contradiction')
                if self.endpoint == '/campaigns/540/leads' and 'campaign_id' in envelope and (type(envelope['campaign_id']) is not int or envelope['campaign_id'] != 540):
                    raise AcquisitionRefused('membership envelope campaign contradiction')
            keys = ('total', 'current_page', 'last_page', 'per_page')
            if any(type(meta.get(k)) is not int for k in keys):
                raise AcquisitionRefused('typed pagination required')
            total, current, last, per = (meta[k] for k in keys)
            if (current != page or not 1 <= page <= last <= self.limits[0]
                    or not 1 <= per <= self.limits[1] or not 0 <= total <= self.limits[1]
                    or last != max(1, (total + per - 1) // per)):
                raise AcquisitionRefused('pagination bounds')
            stable = (total, last, per)
            if self.metadata is not None and stable != self.metadata:
                raise AcquisitionRefused('pagination drift')
            if len(rows) != min(per, max(0, total - (page - 1) * per)):
                raise AcquisitionRefused('incomplete page')
            if any(type(row) is not dict for row in rows):
                raise AcquisitionRefused('object rows required')
            for row in rows:
                if 'workspace_id' in row and (type(row['workspace_id']) is not int or row['workspace_id'] != self.workspace):
                    raise AcquisitionRefused('row workspace contradiction')
                if self.endpoint == '/campaigns/540/leads' and 'campaign_id' in row and (type(row['campaign_id']) is not int or row['campaign_id'] != 540):
                    raise AcquisitionRefused('membership campaign contradiction')
            # Bound nesting before exposing arbitrary provider-shaped JSON.
            def depth(item, level=0):
                if level > 16:
                    raise AcquisitionRefused('JSON depth bound')
                if type(item) is dict:
                    for child in item.values(): depth(child, level + 1)
                elif type(item) is list:
                    for child in item: depth(child, level + 1)
            depth(rows)
            self.metadata = stable
            self.rows.extend(rows)
            self.receipts.append({'page': page, 'sha256': hashlib.sha256(raw).hexdigest(),
                                  'bytes': len(raw), 'observed_at': observed_at})
        except Exception as exc:
            self.failed = True
            if isinstance(exc, AcquisitionRefused): raise
            raise AcquisitionRefused('invalid response encoding or JSON') from None

    def finish(self, *, workspace_id, observed_at, unique_field):
        if self.failed or self.closed:
            raise AcquisitionRefused('assembly terminal')
        self.closed = True
        try:
            self._time(observed_at)
            if type(workspace_id) is not int or workspace_id != self.workspace:
                raise AcquisitionRefused('workspace drift')
            if self.metadata is None or len(self.receipts) != self.metadata[1] or len(self.rows) != self.metadata[0]:
                raise AcquisitionRefused('incomplete collection')
            if unique_field != ('name' if self.endpoint == '/custom-variables' else 'id'):
                raise AcquisitionRefused('explicit identity field required')
            identities = set()
            for row in self.rows:
                identity = row.get(unique_field)
                if unique_field == 'name':
                    if type(identity) is not str or not identity or len(identity) > 64:
                        raise AcquisitionRefused('invalid name')
                    identity = identity.casefold()
                elif type(identity) is not int or identity <= 0:
                    raise AcquisitionRefused('invalid id')
                if identity in identities:
                    raise AcquisitionRefused('cross-page identity alias')
                identities.add(identity)
            result = {'schema': 'bounded-page-assembly/1', 'workspace_id': self.workspace,
                    'complete': True, 'rows': json.loads(json.dumps(self.rows, allow_nan=False)),
                    'receipts': list(self.receipts), 'started_at': self.started,
                    'finished_at': observed_at, 'producer_authenticated': False,
                    'freshness_proven': False, 'readiness': False,
                    'send_allowed': False, 'write_allowed': False}
            if self.endpoint == '/custom-variables':
                result['inventory'] = {'workspace_id': self.workspace, 'complete': True,
                                       'declared_names': [row['name'] for row in self.rows]}
            if self.endpoint == '/campaigns/540/leads':
                result['campaign_id'] = 540
                result['attached_lead_ids'] = [row['id'] for row in self.rows]
            return result
        except Exception:
            self.failed = True
            raise


def decode_single_response(raw, *, route, http_status, workspace_id, lead_id=None):
    """Lossless offline lead/campaign/v1.1 parsing for a future read worker.

    This does not authenticate the caller-supplied route/status/workspace/bytes.
    Missing parser envelope/identity fields refuse; missing title/material authority
    stays explicit. Nothing is filled from a frozen plan or fixture.
    Decimal extras use finite binary floats; exact decimal text is not retained.
    """
    if (type(raw) is not bytes or not raw or len(raw) > 1048576
            or type(http_status) is not int or not 200 <= http_status < 300
            or type(workspace_id) is not int or workspace_id != 10):
        raise AcquisitionRefused('single response boundary')
    is_lead = type(lead_id) is int and 0 < lead_id <= 9007199254740991
    allowed = ('/campaigns/540', '/campaigns/v1.1/540/sequence-steps')
    if route not in allowed and not (is_lead and route == '/leads/' + str(lead_id)):
        raise AcquisitionRefused('single response route')
    if route in allowed and lead_id is not None:
        raise AcquisitionRefused('unexpected lead binding')
    try:
        envelope = json.loads(raw.decode('utf-8'), object_pairs_hook=_object,
                              parse_float=_float,
                              parse_constant=lambda _: (_ for _ in ()).throw(AcquisitionRefused('nonfinite JSON')))
        if type(envelope) is not dict or type(envelope.get('data')) is not dict:
            raise AcquisitionRefused('single object envelope')
        data = envelope['data']
        def walk(item, level=0):
            if level > 16:
                raise AcquisitionRefused('single response depth')
            if type(item) is dict:
                if 'workspace_id' in item and (type(item['workspace_id']) is not int or item['workspace_id'] != 10):
                    raise AcquisitionRefused('single response workspace contradiction')
                for value in item.values(): walk(value, level + 1)
            elif type(item) is list:
                for value in item: walk(value, level + 1)
        walk(envelope)
        missing = []
        if route.startswith('/leads/'):
            if type(data.get('id')) is not int or data['id'] != lead_id:
                raise AcquisitionRefused('single lead identity')
            variables = data.get('custom_variables')
            if type(variables) is not list or len(variables) > 102:
                raise AcquisitionRefused('single lead variable rows')
            # Deliberately preserve duplicate rows for downstream alias refusal.
            for row in variables:
                if (type(row) is not dict or type(row.get('name')) is not str
                        or not row['name'] or len(row['name']) > 64
                        or 'value' not in row or (row['value'] is not None and type(row['value']) is not str)):
                    raise AcquisitionRefused('single lead variable shape')
            missing.append('canonical_identity_binding')
        elif route == '/campaigns/540':
            if (type(data.get('id')) is not int or data['id'] != 540
                    or type(data.get('status')) is not str or not data['status']
                    or type(data.get('total_leads')) is not int or data['total_leads'] < 0):
                raise AcquisitionRefused('single campaign shape')
            missing.append('exhaustive_membership')
        else:
            if type(data.get('sequence_id')) is not int or not 0 < data['sequence_id'] <= 9007199254740991:
                raise AcquisitionRefused('single sequence identity')
            steps = data.get('sequence_steps')
            if type(steps) is not list or not 1 <= len(steps) <= 102:
                raise AcquisitionRefused('single sequence steps')
            ids = set()
            for row in steps:
                if (type(row) is not dict or type(row.get('id')) is not int
                        or row['id'] <= 0 or row['id'] in ids):
                    raise AcquisitionRefused('single sequence step identity')
                ids.add(row['id'])
                # Keep strings/numbers and all extra metadata exactly as supplied.
                # The strict native material contract, not this parser, decides support.
            if 'title' not in data:
                missing.append('sequence_title')
            elif type(data['title']) is not str or not data['title'] or len(data['title'].encode('utf-8')) > 512:
                raise AcquisitionRefused('single sequence title')
            missing.append('native_step_material_validation')
        return {'schema': 'lossless-single-observation/1', 'route': route,
                'workspace_id': workspace_id, 'http_status': http_status,
                'response_sha256': hashlib.sha256(raw).hexdigest(), 'response_bytes': len(raw),
                'data': data, 'missing_authority': missing,
                'producer_authenticated': False, 'freshness_proven': False,
                'snapshot_ready': False, 'readiness': False,
                'send_allowed': False, 'write_allowed': False}
    except Exception as exc:
        if isinstance(exc, AcquisitionRefused): raise
        raise AcquisitionRefused('invalid single response JSON') from None
