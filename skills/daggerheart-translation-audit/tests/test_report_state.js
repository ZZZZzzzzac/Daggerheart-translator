'use strict';
const assert=require('node:assert/strict');
const {createReview,paginateText}=require('../assets/report.js');
const items=[{id:'EX-1',status:'confirmed',text:'example alpha'},{id:'EX-2',status:'uncertain',text:'example beta'},{id:'EX-3',status:'confirmed',text:'example gamma'}];
const options={reportId:'synthetic',progressFormat:'test-progress'};
const values=new Map();const store={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
let a=createReview(items,store,()=>{},options);assert.equal(a.snapshot().current,'EX-1');a.setCompleted('EX-1',true);assert.equal(a.snapshot().current,'EX-2');
a=createReview(items,store,()=>{},options);assert.equal(a.snapshot().completed,1);a.filters({view:'done'});a.setCompleted('EX-1',false);assert.equal(a.snapshot().completed,0);a.filters({view:'todo',status:'uncertain'});assert.deepEqual(a.snapshot().list,['EX-2']);
a.filters({status:'all',query:'none'});assert.equal(a.snapshot().current,null);a.filters({query:''});for(const x of items)a.setCompleted(x.id,true);assert.equal(a.snapshot().current,null);
const progress=a.exportProgress();const b=createReview(items,null,()=>{},options);assert.equal(b.importProgress(JSON.stringify(progress)).added,3);assert.equal(b.importProgress(JSON.stringify(progress)).added,0);
for(const bad of [{...progress,reportId:'other'},{...progress,completedIds:['<script>']},{...progress,completedIds:['EX-1','EX-1']},{...progress,exportedAt:'1'}]){assert.throws(()=>b.importProgress(JSON.stringify(bad)));assert.equal(b.snapshot().completed,3)}
for(const text of ['', 'abc', 'Words and spaces\nNew paragraph\n\nEnd.', '中文🙂👩🏽‍💻 café\n'.repeat(90), 'x'.repeat(300)]){
 for(const size of [1,3,7,50]){const parts=paginateText(text,s=>Array.from(s).length<=size);assert.equal(parts.join(''),text);assert(parts.every(p=>Array.from(p).length<=size));}
}
assert.throws(()=>paginateText('x',()=>false));
console.log('PASS synthetic progress, compatibility, strict imports, Unicode and lossless pagination');
