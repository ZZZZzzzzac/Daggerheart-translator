'use strict';
function createReview(items,storage,onWarning,options){
 const REPORT_ID=options.reportId;const FORMAT=options.progressFormat||"translation-audit-progress";const PREFIX=options.storagePrefix||(FORMAT+":"+REPORT_ID+":");
 const valid=new Set(items.map(x=>x.id));const done=new Set();let current=null,view='todo',status='all',query='';
 const warn=()=>onWarning&&onWarning('浏览器存储不可用或写入失败。本次勾选仍在当前页面有效，但刷新后可能丢失。请及时导出进度JSON。');
 if(storage){try{for(const id of valid){if(storage.getItem(PREFIX+id)==='1')done.add(id)}}catch(e){warn()}}else warn();
 function visible(){return items.filter(x=>(view==='done'?done.has(x.id):!done.has(x.id))&&(status==='all'||x.status===status)&&x.text.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))}
 function reconcile(preferred){const list=visible();if(preferred&&list.some(x=>x.id===preferred))current=preferred;else if(!list.some(x=>x.id===current))current=list[0]?.id||null;return snapshot()}
 function snapshot(){const list=visible();return {list:list.map(x=>x.id),current,index:list.findIndex(x=>x.id===current),completed:done.size,total:items.length,isCompleted:current?done.has(current):false,view,status,query}}
 function persist(id){try{if(!storage)throw Error();if(done.has(id))storage.setItem(PREFIX+id,'1');else storage.removeItem(PREFIX+id)}catch(e){warn()}}
 function setCompleted(id,value){if(!valid.has(id))throw Error('未知问题ID');const before=visible(),i=before.findIndex(x=>x.id===id);if(value)done.add(id);else done.delete(id);persist(id);const after=visible();current=after[Math.min(Math.max(i,0),after.length-1)]?.id||null;return reconcile()}
 function filters(next){if(next.view!==undefined){if(!['todo','done'].includes(next.view))throw Error('无效视图');view=next.view}if(next.status!==undefined){if(!['all','confirmed','uncertain'].includes(next.status))throw Error('无效分类');status=next.status}if(next.query!==undefined)query=String(next.query);return reconcile()}
 function navigate(step){const list=visible(),i=list.findIndex(x=>x.id===current);if(list.length)current=list[Math.max(0,Math.min(list.length-1,i+step))].id;return snapshot()}
 function exportProgress(){return {format:FORMAT,version:1,reportId:REPORT_ID,exportedAt:new Date().toISOString(),completedIds:items.filter(x=>done.has(x.id)).map(x=>x.id)}}
 function importProgress(text){if(typeof text!=='string'||text.length>100000)throw Error('进度文件过大或不是文本');let d;try{d=JSON.parse(text)}catch(e){throw Error('不是有效的JSON文件')}
  if(!d||Array.isArray(d)||typeof d!=='object'||d.format!==FORMAT||d.version!==1||d.reportId!==REPORT_ID)throw Error('文件格式、版本或报告标识不匹配');
  const allowed=new Set(['format','version','reportId','exportedAt','completedIds']);if(Object.keys(d).some(k=>!allowed.has(k)))throw Error('进度文件包含不支持的字段');
  if(typeof d.exportedAt!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(d.exportedAt)||!Number.isFinite(Date.parse(d.exportedAt))||new Date(d.exportedAt).toISOString()!==d.exportedAt||!Array.isArray(d.completedIds)||d.completedIds.length>valid.size)throw Error('进度数据结构不正确');
  const ids=d.completedIds;if(ids.some(id=>typeof id!=='string'||!valid.has(id))||new Set(ids).size!==ids.length)throw Error('进度包含无效或重复的问题ID');
  let added=0;for(const id of ids){if(!done.has(id)){done.add(id);persist(id);added++}}reconcile();return {added,completed:done.size};
 }
 reconcile();return {snapshot,visible,filters,navigate,setCompleted,exportProgress,importProgress};
}
/** Source links are optional for local paired documents; labels follow their provider. */
function sourceAction(f){if(!f||!f.url)return {visible:false,href:null,label:''};const url=new URL(f.url);if(url.protocol!=='https:'||url.username||url.password)throw Error('无效来源链接');const provider=f.provider||url.hostname;return {visible:true,href:f.url,label:'转到 '+provider+' ↗'}}
function applySourceAction(node,f){const source=sourceAction(f);node.hidden=!source.visible;node.setAttribute('aria-disabled',String(!source.visible));node.tabIndex=source.visible?0:-1;node.textContent=source.label;if(source.visible)node.href=source.href;else node.removeAttribute('href')}
/** Project full-source code-point ranges onto explicitly anchored focus segments. */
function projectHighlights(highlights,focusRanges){let offset=0;const result=[];for(const r of focusRanges){for(const h of highlights){const start=Math.max(h.start,r.start),end=Math.min(h.end,r.end);if(start<end)result.push({start:offset+start-r.start,end:offset+end-r.start,reason:h.reason})}offset+=r.end-r.start+2}return result.sort((a,b)=>a.start-b.start)}
/** Render code-point ranges within the provided text; preserve text exactly, never interpret it as HTML. */
function pageHighlightRuns(text,highlights,pageStart){const chars=Array.from(text),end=pageStart+chars.length;let cursor=0;const runs=[];for(const h of highlights){const a=Math.max(pageStart,h.start),b=Math.min(end,h.end);if(a>=b)continue;const start=a-pageStart,stop=b-pageStart;if(start>cursor)runs.push({text:chars.slice(cursor,start).join(''),highlighted:false});runs.push({text:chars.slice(start,stop).join(''),highlighted:true,reason:h.reason});cursor=stop}if(cursor<chars.length)runs.push({text:chars.slice(cursor).join(''),highlighted:false});return runs}
function focusRanges(f,lang){if(f[lang+'_focus_ranges'])return f[lang+'_focus_ranges'];const full=Array.from(f[lang]),parts=f[lang+'_segments']||[f[lang+'_focus']];return parts.map(part=>{const index=f[lang].indexOf(part),start=Array.from(f[lang].slice(0,index)).length;return {start,end:start+Array.from(part).length}})}
/** Render the entire selected text in one independent scroll pane, safely. */
function renderPane(node,text,highlights=[]){const doc=node.ownerDocument;node.replaceChildren();for(const run of pageHighlightRuns(text,highlights,0)){if(run.highlighted){const mark=doc.createElement('mark');mark.textContent=run.text;mark.title=run.reason;node.appendChild(mark)}else node.appendChild(doc.createTextNode(run.text))}node.scrollTop=0;node.scrollLeft=0}
if(typeof module!=='undefined'&&module.exports)module.exports={sourceAction,applySourceAction,createReview,renderPane,projectHighlights,pageHighlightRuns,focusRanges};
if(typeof document!=='undefined'){
 const data=JSON.parse(document.getElementById('report-data').textContent);const el=id=>document.getElementById(id);const byId=new Map(data.findings.map(f=>[f.finding_id,f]));let storage=null,warning='',lastId=null;
 el('progressNotice').textContent=data.progressNotice?' · '+data.progressNotice:'';
 function warn(message){warning=message;el('storageWarning').hidden=false;el('storageWarning').textContent=message;el('moreButton').classList.add('warning');el('moreButton').textContent='保存警告';el('notice').textContent='本次进度可能未保存，请打开“保存警告”导出。'}
 try{storage=window.localStorage}catch(e){warn('浏览器存储不可用；当前页面进度仍有效，请导出JSON备份。')}
 const app=createReview(data.findings.map(f=>({id:f.finding_id,status:f.status,text:[f.finding_id,f.label,f.title,f.id,f.original,f.translation,f.problem,f.suggestion].join('\n')})),storage,warn,data);
 el('reportNotes').textContent=[data.title,data.sourceDescription||data.sourceCutoff||'',data.notes||'','完成标记仅记录审阅进度，不表示译文已修改。来源链接在新标签页打开；本地文本没有外部链接。'].join('\n\n');
 function note(message){el('notice').textContent=message}
 function sourceText(f){const mode=el('contextMode').value;if(mode==='full')return [f.original,f.translation||'【本条尚无译文】'];if(mode==='related'){const related=f.related_contexts||[];let left=related.map(c=>c.label+'\n'+c.original).join('\n\n'),right=related.map(c=>c.label+'\n'+(c.translation||'【暂无译文】')).join('\n\n');const evidence=f.reference_evidence||f.official_evidence;if(evidence){left+='\n\n参考依据\n'+evidence.text;right+='\n\n参考依据说明\n'+evidence.text}return [left||'本项没有额外关联段落。请查看完整条目。',right||'本项没有额外关联段落。请查看完整条目。']}return [f.original_focus,f.translation_focus||'【本条尚无译文】']}
 function render(){const s=app.snapshot(),f=byId.get(s.current);el('progress').textContent=s.completed+'/'+s.total+' 已完成';el('position').textContent=f?(s.view==='done'?'已完成':'待办')+' '+(s.index+1)+'/'+s.list.length:'0项';el('previous').disabled=!f||s.index===0;el('next').disabled=!f||s.index===s.list.length-1;el('complete').disabled=!f;el('complete').textContent=s.isCompleted?'恢复为待办 ↶':'完成，下一条 ✓';applySourceAction(el('sourceLink'),f);
  if(!f){el('evidenceLinks').replaceChildren();el('itemTitle').textContent=data.findings.length===0?'没有待审问题':s.completed===s.total&&s.view==='todo'?'全部已完成':'没有符合条件的条目';el('itemMeta').textContent='更多菜单中可切换已完成或清空筛选';renderPane(el('original'),'');renderPane(el('translation'),'');renderPane(el('judgment'),data.findings.length===0?(data.emptyMessage||'本报告未列出问题。没有问题不自动证明所有文本已审。'):s.completed===s.total?'请导出进度留存。已完成项目可在更多菜单中查看并撤销。':'试试清空搜索、切换分类或返回待办。');lastId=null;return}
  if(lastId!==s.current){el('contextMode').value='full';lastId=s.current}
  el('itemTitle').textContent=f.label||f.title;el('itemTitle').title=f.label||f.title;el('itemMeta').textContent=f.finding_id+' · '+(f.status==='confirmed'?'确认':'待核实')+' · '+f.location;
  el('evidenceLinks').replaceChildren();for(const c of [...(f.related_contexts||[]),f.reference_evidence||f.official_evidence].filter(Boolean)){if(c.url){const a=document.createElement('a');a.href=c.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=c.label||'参考来源';const p=document.createElement('p');p.appendChild(a);el('evidenceLinks').appendChild(p)}}
  const mode=el('contextMode').value;
  const enHighlights=mode==='full'?(f.original_highlights||[]):mode==='focus'?projectHighlights(f.original_highlights||[],focusRanges(f,'original')):[];
  const zhHighlights=mode==='full'?(f.translation_highlights||[]):mode==='focus'?projectHighlights(f.translation_highlights||[],focusRanges(f,'translation')):[];
  el('leftTitle').textContent=(f.original_highlights||[]).length?'原文 · 核对依据':'原文';
  el('rightTitle').textContent=(f.translation_highlights||[]).length?'现译 · 问题或争议处':(f.original_highlights||[]).length?'现译 · 无对应高亮':'现译';
  const texts=sourceText(f);renderPane(el('original'),texts[0],enHighlights);renderPane(el('translation'),texts[1],zhHighlights);
  renderPane(el('judgment'),'问题：'+f.title+'\n'+f.problem+'\n建议：'+f.suggestion);
 }
 el('sourceLink').onclick=event=>{if(el('sourceLink').getAttribute('aria-disabled')==='true')event.preventDefault()};
 el('previous').onclick=()=>{app.navigate(-1);render()};el('next').onclick=()=>{app.navigate(1);render()};el('complete').onclick=()=>{const s=app.snapshot();if(!s.current)return;app.setCompleted(s.current,!s.isCompleted);note(s.isCompleted?'已恢复待办':data.progressNotice||'已完成并从待办隐藏');render()};
 el('contextMode').onchange=()=>render();
 el('moreButton').onclick=()=>{el('more').showModal();el('moreButton').setAttribute('aria-expanded','true')};el('closeMore').onclick=()=>el('more').close();el('more').addEventListener('close',()=>el('moreButton').setAttribute('aria-expanded','false'));
 el('view').onchange=()=>{app.filters({view:el('view').value});render()};el('status').onchange=()=>{app.filters({status:el('status').value});render()};el('query').oninput=()=>{app.filters({query:el('query').value});render()};el('clearFilters').onclick=()=>{el('query').value='';el('status').value='all';app.filters({query:'',status:'all'});render()};
 el('exportProgress').onclick=()=>{try{const blob=new Blob([JSON.stringify(app.exportProgress(),null,2)],{type:'application/json'});const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download='审阅进度-'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),30000);note('已请求下载进度，请确认保存。')}catch(e){warn('导出失败：'+e.message)}};
 el('importProgress').onclick=()=>el('importFile').click();el('importFile').onchange=async()=>{const file=el('importFile').files[0];if(!file)return;try{if(file.size>100000)throw Error('超过100KB');const r=app.importProgress(await file.text());note('已合并 '+r.added+' 项完成');render()}catch(e){warn('导入失败，未应用文件内容：'+e.message)}finally{el('importFile').value=''}};
 requestAnimationFrame(()=>render());
}
