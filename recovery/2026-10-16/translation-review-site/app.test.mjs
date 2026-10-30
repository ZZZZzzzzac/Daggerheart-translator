import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
const source=fs.readFileSync(new URL('./dist/app.mjs',import.meta.url),'utf8').replace(/^import .*?;\n/,'');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.events={};this.attributes={};this.dataset={};this.value='';this.files=[];this.hidden=false;this.textContent='';this.classList={toggle(){},add(){},remove(){}};}
 append(...xs){this.children.push(...xs);} replaceChildren(...xs){this.children=[...xs];} setAttribute(k,v){this.attributes[k]=v;} addEventListener(k,v){this.events[k]=v;} remove(){} click(){return this.events.click?.({target:this});} focus(){}
}
function setup(){
 const elements=new Map(), $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 const tabs=['all','unread','done'].map(x=>{const e=new Element('button');e.dataset.filter=x;return e;});const storage=new Map();
 const context=vm.createContext({document:{getElementById:$,createElement:t=>new Element(t),createTextNode:t=>({textContent:t}),querySelectorAll:()=>tabs,body:new Element('body')},window:{addEventListener(){}},localStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k)||null},crypto:webcrypto,TextEncoder,Blob,URL,setTimeout,console,parseReportJSON:JSON.parse,normalizeReport:async data=>{if(!Array.isArray(data.findings))throw Error('invalid report');return {title:data.title,notice:'notice',description:'description',findings:data.findings.map(f=>({...f,id:f.finding_id}))};}});
 vm.runInContext(source,context);return {context,$,storage,tabs,run:s=>vm.runInContext(s,context)};
}
const tick=()=>new Promise(r=>setTimeout(r,30));
test('synthetic demo loads, Unicode slices are inert, reading completion and undo persist',async()=>{
 const s=setup();await s.$('demo').click();assert.equal(s.run('state.report.findings.length'),2);assert.equal(s.$('workspace').hidden,false);
 const highlighted=s.run(`highlighted('A😀<img>',[{start:1,end:2,reason:'quote'}])`);assert.equal(highlighted.children[1].tagName,'mark');assert.equal(highlighted.children[1].textContent,'😀');assert.equal(highlighted.children[2].textContent,'<img>');
 const actions=s.$('detail').children.at(-1);actions.children[1].click();assert.equal(s.run('state.done.size'),1);assert.equal(s.storage.size,1);const stored=[...s.storage.values()][0];assert.equal(stored.includes('Spend'),false);assert.equal(stored.includes('消耗'),false);
 s.$('detail').children.at(-1).children[1].click();assert.equal(s.run('state.done.size'),0);
});
test('stale report read cannot replace newer demo; failures preserve report',async()=>{
 const s=setup();let resolve;s.context.pending={name:'old.json',size:4,text:()=>new Promise(r=>resolve=r)};s.run('readReport(pending)');await s.$('demo').click();const title=s.run('state.report.title');resolve('{}');await tick();assert.equal(s.run('state.report.title'),title);
 s.context.bad={name:'bad.json',size:2,text:async()=>'{'};await s.run('readReport(bad)');assert.equal(s.run('state.report.title'),title);assert.match(s.$('status').textContent,/无法打开/);
});
test('wrong-document progress rejected, valid progress merges, close invalidates pending reads',async()=>{
 const s=setup();await s.$('demo').click();s.context.badProgress={size:10,text:async()=>JSON.stringify({format:'translation-review-reading-v1',document_sha256:'wrong',completed:[]})};await s.$('progress-file').events.change({target:{files:[s.context.badProgress],value:'x'}});assert.equal(s.run('state.done.size'),0);assert.match(s.$('status').textContent,/无法导入/);
 const progress=s.run('progressObject()');progress.completed=['entry-2'];await s.$('progress-file').events.change({target:{files:[{size:100,text:async()=>JSON.stringify(progress)}],value:'x'}});assert.equal(s.run('state.done.size'),1);
 let resolve;const pending={size:100,text:()=>new Promise(r=>resolve=r)};const operation=s.$('progress-file').events.change({target:{files:[pending],value:'x'}});s.$('close').click();resolve(JSON.stringify(progress));await operation;assert.equal(s.run('state.report'),null);assert.equal(s.$('workspace').hidden,true);
});
test('static content has no executable HTML sinks, upload calls or remote assets',()=>{
 const html=fs.readFileSync(new URL('./dist/index.html',import.meta.url),'utf8');const css=fs.readFileSync(new URL('./dist/styles.css',import.meta.url),'utf8');
 assert.doesNotMatch(source,/innerHTML|outerHTML|insertAdjacentHTML|\bfetch\s*\(|XMLHttpRequest|sendBeacon/);assert.doesNotMatch(html+css,/https?:\/\//);assert.match(html,/connect-src 'none'/);assert.match(html,/lang="zh-CN"/);assert.match(css,/@media\(max-width:600px\)/);
});

test('demo passes the real adapter contract',async()=>{
 const {normalizeReport}=await import('./dist/model.mjs');const s=setup();const result=await normalizeReport(JSON.parse(s.run('JSON.stringify(demo())')));
 assert.equal(result.findings.length,2);assert.equal(result.findings[0].original_highlights[0].start,6);assert.equal(result.findings[0].translation_highlights[0].text,'3');assert.equal(new Set(result.findings.map(f=>f.id)).size,2);
});
