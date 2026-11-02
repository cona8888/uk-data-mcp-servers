"""Edition-specific HPI preparation must not substitute a historical release into a live query."""

import json

import pytest

from uk_data_mcp import civil_housing as h

HEADER = 'Date,Region_Name,Area_Code,Average_Price\n'


def test_historical_price_by_code_and_month(tmp_path):
    a = h.index_file((HEADER+'01/01/2024,Test,E08000025,212345.67\n01/02/2024,Test,E08000025,\n').encode())
    (tmp_path/(h.KEY+'.json')).write_text(json.dumps(a),encoding='utf-8')
    r = h.record('E08000025','2024-01',tmp_path)
    assert r['data'][0]['unit'] == 'GBP' and r['data'][0]['averagePrice'] == 212345.67
    assert r['source']['edition'] == '2025-01' and len(r['source']['source_sha256']) == 64
    assert h.record('E08000025','2024-02',tmp_path)['status'] == 'empty'
    assert h.record('W06000015','2024-01',tmp_path)['status'] == 'empty'
    assert h.record('W06000015','2026-01',tmp_path)['error']['code'] == 'outside_edition'


@pytest.mark.parametrize('data', ['2025-02-01,Test,E08000025,1', '2024-01-01,Test,E08000025,NaN',
                                 '2024-01-01,Test,E08000025,20\n2024-01-01,Test,E08000025,30'])
def test_invalid_or_duplicate_edition_rows(data):
    with pytest.raises(ValueError):
        h.index_file((HEADER+data).encode())


def test_missing_price_edition_is_actionable(tmp_path):
    r = h.record('E08000025','2024-01',tmp_path)
    assert r['error']['code'] == 'not_prepared' and r['operator_action'] == 'uk-civil-data prepare hpi-2025-01'
