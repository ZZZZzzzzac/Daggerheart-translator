'use strict';
// Simulated DOM behavior, not a browser visual acceptance test.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const base=path.join(__dirname,'../assets');
const template=fs.readFileSync(path.join(base,'report.html'),'utf8');
const css=fs.readFileSync(path.join(base,'report.css'),'utf8');
const code=fs.readFileSync(path.join(base,'report.js'),'utf8');
for(const id of ['textPrev','textNext','textPosition','notePrev','noteNext','notePosition'])assert(!template.includes('id="'+id+'"'));
assert(!code.includes('paginateText'));assert(!code.includes('measurePages'));
assert(css.includes('#original,#translation,#judgment{overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable}'));
for(const id of ['original','translation','judgment'])assert(template.includes('id="'+id+'" class="pageText" tabindex="0" role="region"'));
class Node {
 constructor(doc,tag='div'){this.ownerDocument=doc;this.tagName=tag;this.children=[];this.attrs={};this.scrollTop=0;this.scrollLeft=0;this.value='';this.classList={add(){}};}
 set textContent(t){this.children=[];this.text=String(t);}
 get textContent(){return (this.text||'')+this.children.map(c=>c.textContent).join('');}
 replaceChildren(){this.children=[];this.text='';}
 appendChild(n){this.children.push(n);return n;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k];}
 removeAttribute(k){delete this.attrs[k];if(k==='href')delete this.href;}
 addEventListener(){} showModal(){} close(){}
}
const nodes=new Map();const document={getElementById:id=>nodes.get(id),createElement:tag=>new Node(document,tag),createTextNode:text=>{const n=new Node(document,'text');n.textContent=text;return n;}};
for(const match of template.matchAll(/id="([^"]+)"/g))nodes.set(match[1],new Node(document));
const original='Heading 😀\n'+('Full source paragraphs, repeated.\n'.repeat(1500))+'END SOURCE';
const translation='标题 😀\n'+('完整译文段落，重复。\n'.repeat(1200))+'译文末尾';
const a={finding_id:'a',id:'a',label:'A',title:'A',status:'uncertain',location:'test',original,translation,original_focus:'Heading 😀',translation_focus:'标题 😀',original_highlights:[{start:Array.from(original).length-10,end:Array.from(original).length,reason:'last source'}],translation_highlights:[{start:Array.from(translation).length-4,end:Array.from(translation).length,reason:'last translation'}],problem:'Issue\n'.repeat(600),suggestion:'Keep full text',related_contexts:[{label:'Context',original:'related source',translation:'相关译文'}]};
const b={...a,finding_id:'b',id:'b',label:'B',original:'Short source',translation:'短译文',original_focus:'Short source',translation_focus:'短译文',original_highlights:[],translation_highlights:[]};
nodes.get('report-data').textContent=JSON.stringify({reportId:'scroll-test',title:'Scroll test',findings:[a,b],progressNotice:'Reading only'});
const stored=new Map();const window={localStorage:{getItem:k=>stored.get(k),setItem:(k,v)=>stored.set(k,v),removeItem:k=>stored.delete(k)}};
vm.runInNewContext(code,{document,window,requestAnimationFrame:fn=>fn(),URL,Set,Map,Array,JSON,String,Date,Error,Number,console});
const el=id=>nodes.get(id);
assert.equal(el('contextMode').value,'full');
assert.equal(el('original').textContent,original);assert.equal(el('translation').textContent,translation);
assert.equal(el('original').children.filter(n=>n.tagName==='mark').map(n=>n.textContent).join(''),'END SOURCE');
assert.equal(el('translation').children.filter(n=>n.tagName==='mark').map(n=>n.textContent).join(''),'译文末尾');
assert(el('judgment').textContent.includes(a.problem));
el('original').scrollTop=1000;el('translation').scrollTop=37;
assert.equal(el('original').scrollTop,1000);assert.equal(el('translation').scrollTop,37);
el('contextMode').value='related';el('contextMode').onchange();assert(el('original').textContent.includes('related source'));assert(el('translation').textContent.includes('相关译文'));assert.equal(el('original').scrollTop,0);
el('next').onclick();assert.equal(el('original').textContent,'Short source');assert.equal(el('contextMode').value,'full');
el('previous').onclick();assert.equal(el('original').textContent,original);
el('complete').onclick();assert.equal(el('original').textContent,'Short source');assert.equal(stored.size,1);
el('complete').onclick();assert.equal(el('original').textContent,'');assert.equal(el('translation').textContent,'');assert.equal(el('complete').disabled,true);
el('view').value='done';el('view').onchange();assert.equal(el('original').textContent,original);
el('complete').onclick();assert.equal(stored.size,1);
console.log('PASS simulated full-text independent scroll panes, long Unicode, exact highlights, context, card navigation, completion and empty state');
