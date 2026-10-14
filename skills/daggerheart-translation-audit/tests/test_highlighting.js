'use strict';
const assert = require('node:assert/strict');
const {projectHighlights, pageHighlightRuns, focusRanges} = require('../assets/report.js');
const full = '🙂 cost 2; cost 2.';
const evidence = [{start:15,end:16,reason:'Only the second cost is wrong'}];
const runs = pageHighlightRuns(full,evidence,0);
assert.equal(runs.map(r=>r.text).join(''),full);
assert.deepEqual(runs.filter(r=>r.highlighted).map(r=>r.text),['2']);
assert.equal(runs[0].text,'🙂 cost 2; cost ');
const ranges = [{start:10,end:17}];
const projected = projectHighlights(evidence,ranges);
assert.deepEqual(projected,[{start:5,end:6,reason:evidence[0].reason}]);
assert.deepEqual(focusRanges({original:full,original_focus:'cost 2.',original_focus_ranges:ranges},'original'),ranges);
assert.deepEqual(focusRanges({original:full,original_focus:'cost 2.'},'original'),ranges);
assert.deepEqual(pageHighlightRuns('',[],0),[]);
assert.deepEqual(pageHighlightRuns('No invented translation',[],0),[{text:'No invented translation',highlighted:false}]);
// A highlight crossing a removed middle segment must not color the synthetic separator.
const split = projectHighlights([{start:0,end:6,reason:'two selected parts'}],[{start:0,end:2},{start:4,end:6}]);
assert.deepEqual(pageHighlightRuns('ab\n\nef',split,0).map(r=>[r.text,r.highlighted]),[['ab',true],['\n\n',false],['ef',true]]);
const text = 'A😀B\n中<mark>raw</mark>👩‍💻e\u0301\r\nlast';
const chars = Array.from(text);
let cases = 0;
for(let begin=0; begin<chars.length; begin++){
 for(let end=begin+1; end<=chars.length; end+=3){
  const hs=[{start:begin,end,reason:'synthetic evidence'}];
  const rs=pageHighlightRuns(text,hs,0);
  assert.equal(rs.map(r=>r.text).join(''),text);
  assert.equal(rs.filter(r=>r.highlighted).map(r=>r.text).join(''),chars.slice(begin,end).join(''));
  cases++;
 }
}
console.log(`PASS evidence-specific occurrence, omission, focus projection and ${cases} lossless full-text code-point highlight cases`);
