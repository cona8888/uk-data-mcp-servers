"""Semantic checks and a canonical digest of derived indexes, separate from source hashes.

A co-stored digest detects accidental edits, not a malicious actor who can reseal
both file and digest. Keep a trusted digest separately, or rebuild the named release.
"""

import hashlib
import hmac
import json
import math
import re
from datetime import datetime

from .json_safety import validate_json_tree

SCHEMA = 2
HASH = re.compile(r'[a-f0-9]{64}\Z')
COUNT = 10**12


def fail(message):
    raise ValueError('Invalid prepared index: ' + message + '. Re-prepare the named edition.')


def nonnegative(value, label):
    if type(value) is not int or not 0 <= value <= COUNT:
        fail(label + ' must be a non-negative integer')
    return value


def digest(index):
    body = {k: v for k, v in index.items() if k != 'derived_sha256'}
    validate_json_tree(body, max_nodes=2_000_000)
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, allow_nan=False,
                     separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def seal(index):
    index['schema'] = SCHEMA
    index['derived_sha256'] = digest(index)
    return index


def verify(index, expected_digest=None):
    if not isinstance(index, dict) or type(index.get('schema')) is not int or index['schema'] != SCHEMA:
        fail('legacy or unknown schema; old source hashes do not validate derived values')
    for field in ('source_sha256', 'derived_sha256'):
        if not isinstance(index.get(field), str) or not HASH.fullmatch(index[field]):
            fail('missing ' + field)
    actual = digest(index)
    if not hmac.compare_digest(actual, index['derived_sha256']):
        fail('derived-content digest mismatch')
    if expected_digest is not None and not hmac.compare_digest(actual, expected_digest):
        fail('does not match separately trusted derived digest')
    try:
        stamp = datetime.fromisoformat(index['retrieved_at_utc'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            fail('retrieval timestamp must be UTC')
    except (KeyError, TypeError, AttributeError, ValueError):
        fail('invalid retrieval timestamp')
    if not isinstance(index.get('areas'), dict) or not index['areas']:
        fail('missing area records')
    if not isinstance(index.get('licence'), str) or not isinstance(index.get('attribution'), str):
        fail('missing licence or attribution')


def validate_table(index, key, url, census, geography_pattern):
    if (not isinstance(index, dict) or index.get('dataset') != key or index.get('url') != url
            or index.get('area_count') != len(index.get('areas', {}))):
        fail('wrong dataset, source URL or area count')
    verify(index)
    nonnegative(index['area_count'], 'area_count')
    expected_period = '2021-03-21' if census else key[-4:]
    if index.get('reference_period') != expected_period:
        fail('wrong reference period')
    total = 0
    for code, row in index['areas'].items():
        if not geography_pattern.fullmatch(code) or not isinstance(row, dict):
            fail('invalid area code or record')
        if census:
            if not isinstance(row.get('area_name'), str) or not row['area_name'].strip():
                fail('missing census area name')
            cells = row.get('observations')
            if not isinstance(cells, dict) or not 1 <= len(cells) <= 100:
                fail('invalid census observations')
            for cell in cells.values():
                if not isinstance(cell, dict) or set(cell) != {'value', 'as_published'}:
                    fail('invalid census cell')
                published = cell['as_published']
                if not isinstance(published, str) or len(published) > 100:
                    fail('invalid published cell')
                if re.fullmatch(r'\d{1,12}', published):
                    nonnegative(cell['value'], 'census count')
                    if cell['value'] != int(published):
                        fail('census count disagrees with the published value')
                elif cell['value'] is not None or re.fullmatch(r'[+-]?\d+(?:\.\d+)?', published):
                    fail('invalid count or suppression flag')
        else:
            value = nonnegative(row.get('reported_injury_collisions'), 'collision count')
            severity = row.get('by_reported_collision_severity')
            if not isinstance(severity, dict) or set(severity) != {'fatal', 'serious', 'slight', 'unknown'}:
                fail('invalid severity breakdown')
            if value != sum(nonnegative(x, 'severity count') for x in severity.values()):
                fail('severity counts do not sum to collisions')
            total += value
    if not census:
        unassigned = nonnegative(index.get('records_without_usable_district'), 'unassigned count')
        if total + unassigned != nonnegative(index.get('source_records'), 'source_records'):
            fail('national counts do not reconcile')


def validate_housing(index, edition, url):
    verify(index)
    if index.get('edition') != edition or index.get('url') != url:
        fail('wrong HPI edition or source')
    for code, row in index['areas'].items():
        if not re.fullmatch(r'(?:E0[6789]|W06|S12|N09)\d{6}', code) or not isinstance(row, dict):
            fail('invalid HPI geography')
        if not isinstance(row.get('name'), str) or not row['name'].strip():
            fail('missing HPI area name')
        if not isinstance(row.get('months'), dict) or not row['months']:
            fail('missing HPI months')
        for month, value in row['months'].items():
            if not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])', month) or month > edition:
                fail('invalid HPI month')
            if value is not None and (not isinstance(value, str)
                    or not re.fullmatch(r'\d{1,15}(?:\.\d{1,15})?', value)
                    or not math.isfinite(float(value))):
                fail('invalid HPI price')


def cache_error(key, message):
    return {'status': 'error', 'data': [], 'error': {'code': 'invalid_cache', 'message': message},
            'operator_action': 'uk-civil-data prepare ' + key,
            'note': 'No cached value was trusted or substituted. Preserve the file for audit before rebuilding.'}
