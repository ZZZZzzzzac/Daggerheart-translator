'use strict';
// Adapter-specific progressive enhancement in a simulated DOM, not browser QA.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(process.argv[2],'utf8');
const payload=JSON.parse(html.match(/<script id="report-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
assert(html.includes('<main id="app" hidden>'));
assert(html.includes('<div id="static-review" role="main" aria-label='));
class Node {
 constructor(doc,tag='div'){this.ownerDocument=doc;this.tagName=tag;this.children=[];this.attrs={};this.hidden=false;this.scrollTop=0;this.scrollLeft=0;this.value='';this.classList={add(){}};}
 set textContent(t){this.children=[];this.text=String(t);}
 get textContent(){return (this.text||'')+this.children.map(c=>c.textContent).join('');}
 replaceChildren(){this.children=[];this.text='';}
 appendChild(n){this.children.push(n);return n;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k];}
 removeAttribute(k){delete this.attrs[k];if(k==='href')delete this.href;}
 addEventListener(){} showModal(){} close(){}
}
function boot(failRender=false){
 const nodes=new Map(),queued=[];
 const document={getElementById:id=>nodes.get(id),createElement:tag=>{if(failRender)throw Error('simulated render failure');return new Node(document,tag);},createTextNode:text=>{if(failRender)throw Error('simulated render failure');const n=new Node(document,'text');n.textContent=text;return n;}};
 for(const match of html.matchAll(/\sid="([^"]+)"/g))nodes.set(match[1],new Node(document));
 nodes.get('app').hidden=true;
 nodes.get('enhanced-menu').hidden=true;
 nodes.get('report-data').textContent=JSON.stringify(payload);
 const stored=new Map(),window={localStorage:{getItem:k=>stored.get(k),setItem:(k,v)=>stored.set(k,v),removeItem:k=>stored.delete(k)}};
 vm.runInNewContext(code,{document,window,requestAnimationFrame:fn=>queued.push(fn),URL,Set,Map,Array,JSON,String,Date,Error,Number,console});
 assert.equal(nodes.get('app').hidden,true);
 assert.equal(nodes.get('enhanced-menu').hidden,true);
 assert.equal(nodes.get('static-review').hidden,false);
 assert.equal(queued.length,1);
 return {el:id=>nodes.get(id),render:queued[0],stored};
}
const failed=boot(true);
assert.throws(()=>failed.render(),/simulated render failure/);
assert.equal(failed.el('static-review').hidden,false,'failed startup must leave the complete static report visible');
assert.equal(failed.el('app').hidden,true,'partially initialized UI must not replace static content');
assert.equal(failed.el('enhanced-menu').hidden,true,'static report must not expose inactive menu controls');
const good=boot();good.render();
assert.equal(good.el('static-review').hidden,true);
assert.equal(good.el('app').hidden,false);
assert.equal(good.el('enhanced-menu').hidden,false);
const first=payload.findings[0];
assert.equal(good.el('original').textContent,first.original);
assert.equal(good.el('translation').textContent,first.translation||'【本条尚无译文】');
assert.deepEqual(good.el('translation').children.filter(x=>x.tagName==='mark').map(x=>x.textContent),first.translation_highlights.map(x=>x.text));
good.el('next').onclick();
assert.equal(good.el('original').textContent,payload.findings[1].original);
assert.equal(good.el('translation').textContent,payload.findings[1].translation||'【本条尚无译文】');
good.el('previous').onclick();
assert.equal(good.el('translation').textContent,first.translation||'【本条尚无译文】','navigation replaces text rather than duplicating static content');
good.el('complete').onclick();assert.equal(good.stored.size,1);
assert(good.el('progressNotice').textContent.includes('不批准配置'));
assert(good.el('progressNotice').textContent.includes(payload.progressNotice),'top-level gate notice remains visible while navigating or completing child items');
assert.equal(good.el('static-review').hidden,true);
good.el('view').value='done';good.el('view').onchange();good.el('complete').onclick();assert.equal(good.stored.size,0);
console.log('PASS static-first fallback, failed initialization, exact enhanced marks, navigation, completion and undo (simulated DOM)');
