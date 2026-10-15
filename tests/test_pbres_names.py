import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('names', ROOT / 'experiments/context_contract/pbres_names.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(template='职业', version='1.1.0'):
    _, schemas = m.catalog()
    schema = schemas[(template, version)]['schema']
    def blank(s):
        if s['type'] == 'object':
            return {k: blank(s['properties'][k]) for k in s.get('required', [])}
        if s['type'] == 'array':
            return []
        return ''
    data = blank(schema)
    data.update(名称='守护者', 原文='Guardian')
    return {'resources': [{'id': 'r1', 'template': {'id': template, 'version': version}, 'data': data}]}


class NameTests(unittest.TestCase):
    def test_actual_schema_optional_names(self):
        _, schemas = m.catalog()
        self.assertEqual(len(schemas), 15)
        for entry in schemas.values():
            self.assertNotIn('原文', entry['schema']['required'])
        self.assertNotIn('原文', schemas[('玩家卡', '1.0.0')]['schema']['properties'])

    def test_profession_nested_and_hope(self):
        doc = fixture()
        doc['resources'][0]['data']['希望特性'].update(特性名称='不屈', 特性原文='Unyielding')
        doc['resources'][0]['data']['特性'] = [dict(特性名称='无畏', 特性原文='Fearless', 特性描述='描述')]
        before = copy.deepcopy(doc)
        rows = m.extract(doc)['rows']
        self.assertEqual([r['original_pointer'] for r in rows], ['/data/原文', '/data/希望特性/特性原文', '/data/特性/0/特性原文'])
        self.assertEqual(before, doc)

    def test_all_template_shapes_and_roundtrip(self):
        for name, version in m.catalog()[1]:
            if name == '玩家卡':
                continue
            doc = fixture(name, version)
            m.validate(doc, m.extract(doc))

    def test_free_content_not_feature_key(self):
        doc = fixture('自由')
        doc['resources'][0]['data']['内容'] = [dict(名称='触发', 原文='Trigger', 描述='描述')]
        self.assertEqual(m.extract(doc)['rows'][1]['original_pointer'], '/data/内容/0/原文')

    def test_weapon_and_community_distinction(self):
        doc = fixture('武器')
        self.assertEqual(m.extract(doc)['rows'][1]['original_pointer'], '/data/特性原文')
        doc = fixture('社群')
        self.assertEqual(m.extract(doc)['rows'][1]['original_pointer'], '/data/特性/特性原文')

    def test_no_invented_names_for_domain_or_item(self):
        for name in ['领域卡', '物品']:
            self.assertEqual(len(m.extract(fixture(name))['rows']), 1)

    def test_absent_empty_distinct(self):
        doc = fixture()
        rows = m.extract(doc)['rows']
        self.assertEqual(rows[1]['status'], 'absent')
        doc['resources'][0]['data']['希望特性']['特性原文'] = ''
        self.assertEqual(m.extract(doc)['rows'][1]['status'], 'empty')

    def test_loss_invention_parent_pointer_and_order_rejected(self):
        doc = fixture(); expected = m.extract(doc)
        for mutation in ['drop', 'invent', 'parent', 'pointer', 'order']:
            sidecar = copy.deepcopy(expected)
            if mutation == 'drop': sidecar['rows'].pop()
            elif mutation == 'invent': sidecar['rows'][1]['original'] = 'Invented'
            elif mutation == 'parent': sidecar['rows'][0]['resource_id'] = 'r2'
            elif mutation == 'pointer': sidecar['rows'][0]['original_pointer'] = '/data/特性原文'
            else: sidecar['rows'].reverse()
            with self.assertRaises(ValueError): m.validate(doc, sidecar)

    def test_duplicate_and_unknown_version_and_wrong_keys_block(self):
        doc = fixture(); doc['resources'] *= 2
        with self.assertRaises(ValueError): m.extract(doc)
        doc = fixture(); doc['resources'][0]['template']['version'] = '9.0.0'
        with self.assertRaises(ValueError): m.extract(doc)
        doc = fixture(); doc['resources'][0]['data']['希望特性']['原名'] = 'Wrong'
        with self.assertRaises(ValueError): m.extract(doc)

    def test_same_name_occurrences_stay_distinct(self):
        doc = fixture(); feature = dict(特性名称='相同', 特性原文='Same', 特性描述='规则')
        doc['resources'][0]['data']['特性'] = [feature, feature]
        rows = m.extract(doc)['rows']
        self.assertNotEqual(rows[-1]['original_pointer'], rows[-2]['original_pointer'])

    def test_sidecar_does_not_exempt_prose_english_and_dice_links(self):
        doc = fixture(); sidecar = m.extract(doc)
        source = [{'id': 's', 'source': 'Guardian rolls d6. [Rules](#rules)'}]
        self.assertTrue(m.check(doc, sidecar, source, {'units': [{'id': 's', 'translation': '守护者掷 d6。见[规则](#rules)。'}]})['release_allowed'])
        for text in ['守护者 Guardian 掷 d6。见[规则](#rules)。', '守护者掷 d8。']:
            self.assertFalse(m.check(doc, sidecar, source, {'units': [{'id': 's', 'translation': text}]})['release_allowed'])

    def test_prepare_binds_sidecar_and_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'
            m.prepare([{'id': 's', 'source': 'Guardian rolls d6.'}], fixture(), run)
            manifest = m.read(run / 'manifest.json')
            self.assertIn('original-names.json', manifest['prepared_files'])
            self.assertIn('original-name-resources.json', manifest['prepared_files'])
            for name in ['phase1-generate.txt', 'baseline-generate.txt', 'two-pass-packet.json']:
                self.assertIn('独立原名表', (run / name).read_text())
            self.assertEqual(m.read(run / 'delivery-profile.json'), {'allowed_latin': []})

    def test_release_rejects_tampered_sidecar_before_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'run'
            m.prepare([{'id': 's', 'source': 'Guardian rolls d6.'}], fixture(), run)
            sidecar = m.read(run / 'original-names.json')
            sidecar['rows'][0]['original'] = 'Tampered'
            m.write(run / 'original-names.json', sidecar)
            with self.assertRaisesRegex(ValueError, 'prepared delivery input changed: original-names.json'):
                m.gate_module().release(run, development=True)
            self.assertFalse(m.read(run / 'delivery-gate.json')['release_allowed'])

if __name__ == '__main__':
    unittest.main()
