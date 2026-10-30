"""Differential diagnostic-only verification across a bounded synthetic matrix."""
import copy, importlib.util, itertools, json
from pathlib import Path
P = Path(__file__).resolve().parent
R = P.parent / 'Daggerheart-translator-code-trial'
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
old = load('quantity_before', P / 'quantity_risks.before.py')
new = load('quantity_after', R / 'experiments/context_contract/quantity_risks.py')
texts = ['', 'Rest.', '休息。', '10/17', '10/18', '17/10', '11/18', '1.5', '1/2',
         'half', '一半', '½', '²', 'Ⅲ', '٢', '2', '3', '10', '17', 'two', '二',
         '+3', '-3', '2d6', '3d6', '10/17; 2', '10/17; 3', '10/17; 10/18',
         '2; 3', '3; 2']
cfg = {'version': new.VERSION, 'scopes': [{'id': 'matrix', 'unit_id': 's',
        'source': {'kind': 'field', 'pointer': '/quantity_fields/value'},
        'translation': {'kind': 'field', 'pointer': '/quantity_fields/value'}}]}
def no_parser(_): raise AssertionError('Plain fields must not need a parser.')
rows = []; removed = 0
for source, target in itertools.product(texts, repeat=2):
    sources = [{'id': 's', 'source': source, 'quantity_fields': {'value': source}}]
    targets = {'units': [{'id': 's', 'translation': target, 'quantity_fields': {'value': target}}]}
    before = old.scan(sources, targets, cfg, no_parser)
    after = new.scan(sources, targets, cfg, no_parser)
    row = before['scopes'][0]
    dedup = not row['source']['tokens'] and not row['translation']['tokens'] and bool(row['source']['uncertain']) and bool(row['translation']['uncertain'])
    expected = copy.deepcopy(before)
    if dedup:
        expected['scopes'][0]['risks'] = [r for r in expected['scopes'][0]['risks'] if r['kind'] != 'no_comparable_quantities']
        expected['risk_count'] -= 1; removed += 1
    assert after == expected, (source, target)
    assert before['status'] == after['status'] and before['release_allowed'] == after['release_allowed']
    assert after['semantic_verified'] is False
    rows.append({'source': source, 'translation': target, 'risks_before': before['risk_count'],
                 'risks_after': after['risk_count'], 'status_unchanged': True,
                 'release_unchanged': True, 'all_evidence_unchanged': True,
                 'deduplicated': dedup})
result = {'pair_count': len(rows), 'deduplicated_pairs': removed,
          'unchanged_release_decisions': len(rows), 'unchanged_evidence_pairs': len(rows),
          'synthetic_only': True, 'population_quality_claim': False, 'cases': rows}
(P / 'differential-matrix.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'cases'}))
