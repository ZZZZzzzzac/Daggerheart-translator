import { normalizeReport, parseReportJSON } from './model.mjs';
const $ = id => document.getElementById(id);
const MAX_BYTES = 10 * 1024 * 1024;
const state = { report: null, digest: '', done: new Set(), selected: null, filter: 'all', search: '', generation: 0, progressGeneration: 0, filename: '' };
const make = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; };
function status(message, error=false) { $('status').textContent=message; $('status').classList.toggle('error',error); }
function canonical(v) { if (Array.isArray(v)) return '['+v.map(canonical).join(',')+']'; if(v && typeof v==='object') return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}'; return JSON.stringify(v); }
async function hash(v) { const bytes = await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v))); return [...new Uint8Array(bytes)].map(n=>n.toString(16).padStart(2,'0')).join(''); }
const storageKey = () => 'translation-review-reading-v1:'+state.digest;
function progressObject() { return { format:'translation-review-reading-v1', document_sha256:state.digest, completed:[...state.done].sort(), exported_at:new Date().toISOString() }; }
function validateProgress(value) {
 if (!value || value.format!=='translation-review-reading-v1' || value.document_sha256!==state.digest || !Array.isArray(value.completed)) throw Error('进度格式不正确，或不属于当前文件内容。');
 const ids=new Set(state.report.findings.map(f=>f.id));
 if(value.completed.some(id=>typeof id!=='string'||!ids.has(id)) || new Set(value.completed).size!==value.completed.length) throw Error('进度包含未知或重复的条目标识。');
 return new Set(value.completed);
}
function saveProgress() { try { localStorage.setItem(storageKey(),JSON.stringify(progressObject())); return true; } catch { status('浏览器无法保存进度。当前标记仍有效，请导出进度备份。',true); return false; } }
async function loadData(data, filename, token) {
 const report=await normalizeReport(data); const digest=await hash(data);
 if(token!==state.generation) return;
 // Only opaque positional IDs persist; the full content hash binds their meaning.
 report.findings=report.findings.map((finding,index)=>({...finding,id:'entry-'+(index+1)}));
 state.report=report; state.digest=digest; state.done=new Set(); state.selected=report.findings[0]?.id??null;state.filter='all';state.search='';state.filename=filename;
 let restored=false, storageWarning=false;
 try { const saved=localStorage.getItem(storageKey()); if(saved){state.done=validateProgress(parseReportJSON(saved));restored=true;} } catch { storageWarning=true; }
 $('search').value='';$('workspace').hidden=false;document.body.classList.add('has-report');
 $('report-title').textContent=report.title;$('filename').textContent=filename+' · '+report.findings.length+' 条 · 文件指纹 '+digest.slice(0,12);
 $('report-notice').textContent=report.notice;$('description').textContent=report.description;
 render();status(storageWarning?'文件已打开。未能读取本地进度，您可以导入进度备份。':`${filename} 已在本地打开。${restored?'已恢复此文件的阅读进度。':'文件内容不会上传。'}`,storageWarning);
}
async function readReport(file) {
 if(!file) return;const token=++state.generation;++state.progressGeneration;
 try { if(file.size>MAX_BYTES) throw Error('文件超过 10 MB，请拆分报告后再试。');status('正在本地读取并验证文件…');const text=await file.text();if(token!==state.generation)return;await loadData(parseReportJSON(text),file.name,token); }
 catch(e){if(token===state.generation)status('无法打开文件：'+e.message+' 已打开的报告保持不变。',true);}
}
function visible() {return state.report.findings.filter(f=>(state.filter==='all'||(state.filter==='done')===state.done.has(f.id))&&(!state.search||[f.title,f.location,f.problem,f.original,f.translation].join('\n').toLocaleLowerCase().includes(state.search)));}
function highlighted(text, spans) {
 const node=make('div','passage');const points=Array.from(text);let pos=0;
 for(const span of spans||[]){node.append(document.createTextNode(points.slice(pos,span.start).join('')));const mark=make('mark','',points.slice(span.start,span.end).join(''));mark.title=span.reason||'报告中的精确证据';node.append(mark);pos=span.end;}
 node.append(document.createTextNode(points.slice(pos).join('')));if(!text)node.append(make('p','muted','未提供此侧文本；不推断对应内容。'));return node;
}
function textGrid(f, marks=true) { const grid=make('div','text-grid');for(const [side,label] of [['original','原文 / SOURCE'],['translation','现译 / TRANSLATION']]) {const col=make('div','text-column '+side);col.append(make('div','column-label',label),highlighted(f[side],marks?f[side+'_highlights']:[]));grid.append(col);}return grid; }
function button(text,cls,fn,disabled=false){const b=make('button','button '+cls,text);b.type='button';b.disabled=disabled;b.addEventListener('click',fn);return b;}
function render() {
 if(!state.report)return;const all=state.report.findings, rows=visible();
 if(!rows.some(f=>f.id===state.selected))state.selected=rows[0]?.id??null;
 $('count-all').textContent=all.length;$('count-done').textContent=state.done.size;$('count-unread').textContent=all.length-state.done.size;
 document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===state.filter)));
 $('position').textContent=rows.length+' 条';$('progress-label').textContent=`已读 ${state.done.size} / ${all.length} 条`;$('progress-bar').max=all.length||1;$('progress-bar').value=state.done.size;
 const indexes=new Map(all.map((f,i)=>[f.id,i]));
 const list=$('finding-list');list.replaceChildren();
 rows.forEach(f=>{const b=make('button','finding-button');b.type='button';b.setAttribute('aria-current',String(f.id===state.selected));b.append(make('span','number',String(indexes.get(f.id)+1).padStart(2,'0')));const c=make('span');c.append(make('span','item-title',f.title),make('small','',state.done.has(f.id)?'✓ 已读':'○ 待阅读'));b.append(c);b.addEventListener('click',()=>{state.selected=f.id;render();});list.append(b);});
 const detail=$('detail');detail.replaceChildren();
 if(!rows.length){list.append(make('p','empty','没有符合筛选的条目'));detail.append(make('div','empty',all.length?'当前筛选下没有条目。试试「全部」或清除搜索。':'报告没有可显示条目。空队列不代表审核通过。'));return;}
 const i=rows.findIndex(f=>f.id===state.selected),f=rows[i],head=make('div','detail-head');head.append(make('span','badge',state.done.has(f.id)?'已读 · 未作审批':'待阅读 · 证据快照'),make('h3','',f.title),make('div','muted',f.location));detail.append(head,textGrid(f));
 const evidence=make('div','evidence');evidence.append(make('h4','','待核对事项'),make('p','',f.problem||'未提供说明。'));if(f.suggestion)evidence.append(make('h4','','建议'),make('p','',f.suggestion));detail.append(evidence);
 for(const context of f.related_contexts||[]){const section=make('details','context');section.append(make('summary','',context.label||'关联上下文'),textGrid(context,false));detail.append(section);}
 const actions=make('div','detail-actions'),nav=make('div','navigation');nav.append(button('← 上一条','secondary',()=>{state.selected=rows[i-1].id;render();},i===0),button('下一条 →','secondary',()=>{state.selected=rows[i+1].id;render();},i===rows.length-1));
 actions.append(nav,button(state.done.has(f.id)?'撤销已读':'标记已读 ✓',state.done.has(f.id)?'secondary':'primary',()=>{const wasDone=state.done.has(f.id);wasDone?state.done.delete(f.id):state.done.add(f.id);++state.progressGeneration;const saved=saveProgress();render();if(saved)status(wasDone?'已撤销阅读标记。':'已记录阅读进度。这不表示批准配置或确认译文正确。');}));detail.append(actions);
}
$('report-file').addEventListener('change',e=>{readReport(e.target.files[0]);e.target.value='';});
const drop=$('dropzone');for(const event of ['dragover','dragenter'])drop.addEventListener(event,e=>{e.preventDefault();drop.classList.add('dragging');});for(const event of ['dragleave','drop'])drop.addEventListener(event,e=>{e.preventDefault();drop.classList.remove('dragging');});drop.addEventListener('drop',e=>{if(e.dataTransfer.files.length!==1){status('请一次选择一份 JSON 报告。',true);return;}readReport(e.dataTransfer.files[0]);});
// Avoid accidental navigation if a local file is dropped outside the import panel.
window.addEventListener('dragover',e=>e.preventDefault());window.addEventListener('drop',e=>e.preventDefault());
document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{state.filter=b.dataset.filter;render();}));$('search').addEventListener('input',e=>{state.search=e.target.value.trim().toLocaleLowerCase();render();});
$('close').addEventListener('click',()=>{++state.generation;++state.progressGeneration;state.report=null;state.digest='';state.done=new Set();$('workspace').hidden=true;$('finding-list').replaceChildren();$('detail').replaceChildren();for(const id of ['report-title','filename','report-notice','description'])$(id).textContent='';document.body.classList.remove('has-report');status('报告已关闭。已保存的阅读进度仍保留在此浏览器中。');$('report-file').focus();});
$('export').addEventListener('click',()=>{if(!state.report)return;const blob=new Blob([JSON.stringify(progressObject(),null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const a=make('a');a.href=url;a.download='reading-progress-'+state.digest.slice(0,12)+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);status('已发起进度下载。备份只包含文件指纹和阅读标记，不包含原译文。');});
$('progress-file').addEventListener('change',async e=>{const file=e.target.files[0];e.target.value='';if(!file||!state.report)return;const generation=state.generation,token=++state.progressGeneration;try{if(file.size>MAX_BYTES)throw Error('进度文件超过 10 MB。');const text=await file.text();if(generation!==state.generation||token!==state.progressGeneration)return;const imported=validateProgress(parseReportJSON(text));state.done=new Set([...state.done,...imported]);const saved=saveProgress();render();if(saved)status('已合并此文件的阅读进度；现有已读标记予以保留。');}catch(error){if(generation===state.generation&&token===state.progressGeneration)status('无法导入进度：'+error.message+' 当前进度未改变。',true);}});
$('demo').addEventListener('click',async()=>{const token=++state.generation;++state.progressGeneration;try{await loadData(demo(),'合成演示 · 非实际翻译资料',token);}catch(e){if(token===state.generation)status('演示无法打开：'+e.message,true);}});
function demo(){const original='Spend 2 sparks to light the lantern. The light lasts for one minute.';const translation='消耗3点火花点亮灯笼。光芒持续一分钟。';return {schemaVersion:1,reportId:'synthetic-lantern-demo-v1',title:'灯笼小记 · 合成审阅演示',progressNotice:'本演示为虚构文字，仅展示阅读与证据定位。完成只记录阅读进度，不证明语义正确。',sourceDescription:'2 条合成示例：数量差异及条件范围。没有使用任何真实项目文本。',findings:[{finding_id:'demo-quantity',title:'点亮灯笼需要多少火花？',location:'演示 / 灯笼 / 第 1 段',problem:'原文写 2，现译写 3。请核对完整上下文，判断差异是否需要修订。',suggestion:'先确认消耗的主体和条件，再核对数量。此页面不修改译文。',original,translation,original_highlights:[{start:6,end:7,text:'2',reason:'原文数量'}],translation_highlights:[{start:2,end:3,text:'3',reason:'译文数量'}],related_contexts:[{label:'查看完整上下文 · 合成演示',original:'A traveler carries a small lantern.\n'+original,translation:'一位旅人携带一盏小灯笼。\n'+translation}]},{finding_id:'demo-condition',title:'光芒的效果是否带有条件？',location:'演示 / 灯笼 / 第 2 段',problem:'两侧都提到路径，但请核对译文是否保留了原文的触发条件。',suggestion:'结合前后文人工判断。未提供精确证据偏移，因此不猜测高亮。',original:'While the lantern is lit, you can see the hidden path.',translation:'你可以看见隐藏的小路。',original_highlights:[],translation_highlights:[],related_contexts:[]}]};}
