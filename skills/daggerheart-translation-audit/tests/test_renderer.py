import copy,importlib.util,json,pathlib,unittest,re
BASE=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('report_renderer',BASE/'scripts/render_report.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def sample():
    f=dict(finding_id='TEST-001',id=1,url='https://example.org/item/1',title='Example rule',label='Example ability',status='confirmed',severity='high',problem='Example issue',suggestion='Example correction',original='When you act, spend 1 resource.',translation='行动时，花费1资源。',original_focus='When you act, spend 1 resource.',translation_focus='行动时，花费1资源。',location='Example 1')
    return dict(schemaVersion=1,reportId='synthetic-audit',title='Example report',sourceCutoff='Legacy optional description',findings=[f])
class RendererTests(unittest.TestCase):
    def test_round_trip_and_offline(self):
        d=sample();s=m.render(d);body=re.search(r'<script id="report-data" type="application/json">(.*?)</script>',s,re.S).group(1);self.assertEqual(json.loads(body),d);self.assertNotIn('<script src=',s);self.assertIn('target="_blank" rel="noopener noreferrer"',s)
    def test_primary_actions_are_together_in_order(self):
        s=m.render(sample());header=s.split('<header>',1)[1].split('</header>',1)[0]
        footer=s.split('<footer',1)[1].split('</footer>',1)[0]
        self.assertNotIn('id="sourceLink"',header)
        ordered=['id="previous"','id="next"','id="complete"','id="sourceLink"']
        positions=[footer.index(token) for token in ordered]
        self.assertEqual(positions,sorted(positions))
        self.assertEqual(s.count('id="sourceLink"'),1)
        self.assertIn('target="_blank" rel="noopener noreferrer"',footer)
        self.assertIn('aria-disabled="true" tabindex="-1"',footer)
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

class GenericRendererTests(unittest.TestCase):
    def test_local_pair_without_link_or_numeric_id(self):
        d=sample();f=d['findings'][0];f.pop('url');f['id']='manual:section-a'
        self.assertIn('manual:section-a',m.render(d))
    def test_optional_provider(self):
        d=sample();d['findings'][0]['provider']='Document portal'
        self.assertIn('Document portal',m.render(d))
    def test_zero_findings_is_not_a_fake_finding(self):
        d=sample();d.update(findings=[],emptyMessage='All three source pairs reviewed; no findings.')
        rendered=m.render(d)
        body=re.search(r'<script id="report-data" type="application/json">(.*?)</script>',rendered,re.S).group(1)
        self.assertEqual(json.loads(body)['findings'],[])
        self.assertIn('All three source pairs reviewed',rendered)
    def test_invalid_optional_links(self):
        for url in ('https://','https://user:secret@example.org',None):
            d=sample();d['findings'][0]['url']=url
            self.assertRaises(ValueError,m.render,d)

    def test_local_reference_without_public_url(self):
        d=sample();d['findings'][0]['reference_evidence']={'text':'Local manual, page 2, revision 1'}
        self.assertIn('Local manual, page 2',m.render(d))
    def test_related_reference_rejects_unsafe_urls(self):
        d=sample();d['findings'][0]['reference_evidence']={'text':'Context','url':'javascript:alert(1)'}
        self.assertRaises(ValueError,m.render,d)

    def test_report_requires_no_source_or_capture_metadata(self):
        d=sample();d.pop('sourceCutoff');d['findings'][0].pop('url')
        self.assertIn('report-data',m.render(d))

if __name__=='__main__':unittest.main()
