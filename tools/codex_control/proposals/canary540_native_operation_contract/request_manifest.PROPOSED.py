"""Pure exact request slots for the prepared scope; never an approval/grant."""
import hashlib
import json


class ManifestRefused(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def build_manifest(lead_ids):
    if (type(lead_ids) is not list or len(lead_ids) != 4
            or any(type(x) is not int or not 0 < x <= 9007199254740991 for x in lead_ids)
            or len(set(lead_ids)) != 4):
        raise ManifestRefused('exact four identity slots required')
    pairs = [('/users', None)] + [('/leads/' + str(x), None) for x in lead_ids]
    pairs.append(('/campaigns/540', None))
    pairs.extend(('/campaigns/540/leads', page) for page in range(1, 9))
    pairs.append(('/campaigns/v1.1/540/sequence-steps', None))
    pairs.extend(('/campaigns/540/sender-emails', page) for page in range(1, 9))
    pairs.extend(('/custom-variables', page) for page in range(1, 9))
    pairs.append(('/users', None))
    return [dict(ordinal=n, route=route, page=page)
            for n, (route, page) in enumerate(pairs, 1)]


def require_request(lead_ids, request):
    if (type(request) is not dict or set(request) != {'ordinal', 'route', 'page'}
            or type(request['ordinal']) is not int or not 1 <= request['ordinal'] <= 32
            or type(request['route']) is not str
            or (request['page'] is not None and type(request['page']) is not int)):
        raise ManifestRefused('request slot schema')
    expected = build_manifest(lead_ids)[request['ordinal'] - 1]
    if digest(request) != digest(expected):
        raise ManifestRefused('request differs from bound slot')
    return expected
