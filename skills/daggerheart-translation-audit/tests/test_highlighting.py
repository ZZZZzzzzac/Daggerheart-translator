import pathlib,importlib.util,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('highlight_renderer',ROOT/'scripts/render_report.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def data():
    text='🙂 cost 2; cost 2.'
    return dict(schemaVersion=1,reportId='test',title='Test',sourceCutoff='test',findings=[dict(finding_id='T1',id=1,url='https://example.org/1',title='cost',label='test',status='confirmed',severity='high',problem='second cost',suggestion='correct',original=text,translation='',original_focus='cost 2.',translation_focus='',location='test',original_focus_ranges=[dict(start=10,end=17)],translation_focus_ranges=[dict(start=0,end=0)],original_highlights=[dict(start=15,end=16,text='2',reason='second cost')],translation_highlights=[])])
class HighlightTests(unittest.TestCase):
    def test_valid_code_point_and_empty_omission(self):self.assertIn('original_highlights',m.render(data()))
    def test_range_validation(self):
        for start,end in [(-1,2),(3,3),(True,3),(0,100)]:
            d=data();d['findings'][0]['original_highlights']=[dict(start=start,end=end,reason='x')];self.assertRaises(ValueError,m.render,d)
    def test_wrong_claimed_text(self):
        d=data();d['findings'][0]['original_highlights'][0]['text']='bad';self.assertRaises(ValueError,m.render,d)
    def test_overlapping_highlights(self):
        d=data();d['findings'][0]['original_highlights']=[dict(start=1,end=5,reason='x'),dict(start=4,end=8,reason='y')];self.assertRaises(ValueError,m.render,d)
    def test_ambiguous_focus_requires_anchor(self):
        d=data();f=d['findings'][0];f['original_focus']='cost 2';del f['original_focus_ranges'];self.assertRaises(ValueError,m.render,d)
    def test_overlapping_substring_is_ambiguous(self):
        d=data();f=d['findings'][0];f.update(original='aaa',original_focus='aa',original_highlights=[]);del f['original_focus_ranges'];self.assertRaises(ValueError,m.render,d)
    def test_inferred_segments_cannot_reverse_source(self):
        d=data();f=d['findings'][0];f.update(original='first second',original_focus='second\n\nfirst',original_segments=['second','first'],original_highlights=[]);del f['original_focus_ranges'];self.assertRaises(ValueError,m.render,d)
    def test_wrong_focus_anchor(self):
        d=data();d['findings'][0]['original_focus_ranges'][0]['start']=0;self.assertRaises(ValueError,m.render,d)
if __name__=='__main__':unittest.main()
