import copy,importlib.util,json,pathlib,unittest,re
BASE=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('report_renderer',BASE/'scripts/render_report.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sample():
    f=dict(finding_id='TEST-001',id=1,url='https://example.org/item/1',title='Example rule',label='Example ability',status='confirmed',severity='high',problem='Example issue',suggestion='Example correction',original='When you act, spend 1 resource.',translation='行动时，花费1资源。',original_focus='When you act, spend 1 resource.',translation_focus='行动时，花费1资源。',location='Example 1')
    return dict(schemaVersion=1,reportId='synthetic-audit',title='Example report',sourceCutoff='Example snapshot',findings=[f])
class RendererTests(unittest.TestCase):
    def test_round_trip_and_offline(self):
        d=sample();s=m.render(d);body=re.search(r'<script id="report-data" type="application/json">(.*?)</script>',s,re.S).group(1);self.assertEqual(json.loads(body),d);self.assertNotIn('<script src=',s);self.assertIn('target="_blank" rel="noopener noreferrer"',s)
    def test_script_injection_escaped(self):
        d=sample();d['findings'][0]['problem']='</script><img src=x onerror=alert(1)> __JS__';s=m.render(d);self.assertNotIn('<img src=x',s);self.assertIn('\\u003c/script',s);self.assertIn('__JS__',s)
    def test_missing_fields(self):
        d=sample();del d['findings'][0]['original'];self.assertRaises(ValueError,m.render,d)
    def test_bad_url(self):
        for url in ('javascript:alert(1)','data:text/html,x','http://example.org'):
            d=sample();d['findings'][0]['url']=url;self.assertRaises(ValueError,m.render,d)
    def test_duplicate_stable_ids(self):
        d=sample();d['findings'].append(copy.deepcopy(d['findings'][0]));self.assertRaises(ValueError,m.render,d)
    def test_invalid_focus(self):
        d=sample();d['findings'][0]['original_focus']='invented';self.assertRaises(ValueError,m.render,d)
    def test_segmented_focus(self):
        d=sample();f=d['findings'][0];f.update(original_segments=['When you act','1 resource.'],original_focus='When you act\n\n1 resource.');self.assertTrue(m.render(d))
    def test_optional_storage_types(self):
        d=sample();d['storagePrefix']={};self.assertRaises(ValueError,m.render,d)
    def test_compatible_storage_names_are_preserved(self):
        d=sample();d.update(reportId='stable-report',progressFormat='legacy-format',storagePrefix='legacy-format:stable-report:');s=m.render(d);self.assertIn('legacy-format:stable-report:',s)
if __name__=='__main__':unittest.main()
