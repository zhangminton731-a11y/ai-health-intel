(()=>{
'use strict';
const D=JSON.parse(document.getElementById('payload').textContent);
const $=s=>document.querySelector(s);
const topicNames={hospital:'临床医疗',consumer:'消费健康',research:'研究证据',business:'商业动态',regulation:'监管进展'};
const sectionCategories={research:{all:'全部',papers:'论文精选',methods:'工具方法',policy:'政策动态'},industry:{all:'全部',products:'新品方案',technology:'技术进展',business:'融资合作',regulation:'市场准入'}};
const selectedCategory={research:'all',industry:'all'};
const stageNames={design:'研究设计',data:'数据处理',analysis:'AI 分析',validation:'研究验证'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=u=>{try{const x=new URL(u);return /^https?:$/.test(x.protocol)?x.href:'#';}catch{return '#';}};
const now=new Date();
const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
const todayMs=Date.parse(today+'T00:00:00Z');
const isCurrent=i=>{const age=(todayMs-Date.parse(i.date+'T00:00:00Z'))/86400000;return i.freshness==='fresh'&&i.tier!=='archive'&&age>=0&&age<=10;};
const current=D.items.filter(isCurrent),byId=Object.fromEntries(current.map(i=>[i.id,i]));
const history=(D.historyItems||[]).filter(i=>{const age=(todayMs-Date.parse(i.date+'T00:00:00Z'))/86400000;return age>=0&&age<=20&&!byId[i.id];});
const archiveById={...Object.fromEntries(history.map(i=>[i.id,i])),...byId};
const searchText=new Map(Object.values(archiveById).map(i=>[i.id,[i.t,i.te,i.s,i.se,i.src].join(' ').toLowerCase()]));
const hot=D.hot30.filter(i=>byId[i.id]);

const collected=Date.parse(D.generatedAt),ageHours=(now-collected)/3600000;
const cstHour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Shanghai',hour:'2-digit',hourCycle:'h23'}).format(now));
let warning='';
if(!Number.isFinite(collected)||ageHours>36)warning='数据更新已延迟，以下内容来自最近成功批次。请核对原文日期，稍后再查看更新。';
else if(D.asOf<today&&cstHour>=9)warning='今天的早间更新尚未完成，当前展示最近成功批次。';

if(warning){$('#staleNotice').textContent=warning;$('#staleNotice').hidden=false;}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,3200);}
async function copy(value,message){try{await navigator.clipboard.writeText(value);toast(message);return true;}catch{toast('复制未成功，请长按选中页面文字复制。');return false;}}

const archiveMonths=(D.archiveMonths||[]).filter(m=>/^\d{4}-(0[1-9]|1[0-2])$/.test(m.month));
const monthlyData=new Map(),archiveRequests=new Map();
function loadArchive(month){
 if(monthlyData.has(month))return Promise.resolve(monthlyData.get(month));
 if(!archiveMonths.some(m=>m.month===month))return Promise.reject(Error('Unknown month'));
 if(!archiveRequests.has(month))archiveRequests.set(month,(async()=>{
  const response=await fetch('api/v1/archive/'+month+'.json');if(!response.ok)throw Error('Archive unavailable');
  const data=await response.json();if(data.month!==month||data.kind!=='retrospective'||!Array.isArray(data.items)||!Array.isArray(data.editions))throw Error('Invalid archive');
  monthlyData.set(month,data);return data;
 })().finally(()=>archiveRequests.delete(month)));
 return archiveRequests.get(month);
}
function awaitArchive(month,target,rerender){
 const hash=location.hash;target.innerHTML='<p class="empty" role="status">正在载入月度资料…</p>';
 loadArchive(month).then(()=>{if(location.hash===hash)rerender();}).catch(()=>{if(location.hash!==hash)return;target.innerHTML='<div class="empty" role="alert">月度资料暂时无法载入。<br><button class="button secondary" type="button">重试</button></div>';target.querySelector('button').onclick=()=>awaitArchive(month,target,rerender);});
}
function articleAudience(i,section){return ['research','industry'].includes(section)&&(i.sections||[]).includes(section)?section:(i.sections||[]).includes('research')?'research':'industry';}
function articleHref(i,section){return '#article?'+new URLSearchParams({id:i.id,section:articleAudience(i,section),...(i.archiveMonth?{month:i.archiveMonth}:{})});}
function renderArticle(params){
 const month=params.get('month');if(month&&archiveMonths.some(m=>m.month===month)&&!monthlyData.has(month)){awaitArchive(month,$('#articleReader'),()=>renderArticle(params));return;}
 const id=params.get('id'),i=month?monthlyData.get(month)?.items.find(i=>i.id===id):(Object.hasOwn(archiveById,id)?archiveById[id]:null);
 if(!i){$('#articleReader').innerHTML='<a class="text-link" href="#jingxuan">← 返回医学科研</a><h1>这篇内容暂不可用</h1><p class="muted">请返回信息流查看当前收录的内容。</p>';return;}
 const audience=articleAudience(i,params.get('section')),home=audience==='research'?'jingxuan':'industry',reason=i.reasons?.[audience],url=safeUrl(i.u);
 $('#articleReader').innerHTML=`<a class="text-link" href="#${home}${month?'?month='+encodeURIComponent(month):''}">← 返回${audience==='research'?'医学科研':'产业前沿'}</a><h1>${esc(i.t||i.te)}</h1><div class="meta"><span>${esc(i.src)}</span><span class="pill">${esc(i.sourceType)}</span><time>${esc(i.date)}</time></div>${reason?`<section class="reader-reason"><h2>推荐理由</h2><p>${esc(reason)}</p></section>`:''}<section class="reader-summary"><h2>内容摘要</h2><p>${esc(i.s||i.se||'来源未提供摘要，请前往来源阅读。')}</p></section><div class="reader-source">${url!=='#'?`<a class="button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">前往来源阅读全文 ↗</a>`:'<p class="muted">原文链接暂不可用。</p>'}</div>`;
 document.querySelectorAll(`.nav-link[href="#${home}"],.mobile-nav a[href="#${home}"]`).forEach(a=>a.setAttribute('aria-current','page'));
}
function score(i){return Number.isFinite(i.rel)?Math.round(Math.max(0,Math.min(98,i.rel))):'待评';}
function excerpt(i,limit=210){const text=(i.s||i.se||'来源未提供摘要，请阅读原文。').trim();if(text.length<=limit)return text;const head=text.slice(0,limit);const stop=Math.max(head.lastIndexOf('。'),head.lastIndexOf('. '),head.lastIndexOf('；'));return stop>limit/2?head.slice(0,stop+1):head+'…';}
function hotArtwork(i){
 const text=[i.te,...(i.topics||[])].join(' ').toLowerCase();
 const drawing=/wearable|glucose|cgm|diabet|smartwatch/.test(text)?'<rect x="141" y="22" width="78" height="190" rx="28" fill="#d1e4e5"/><rect x="126" y="63" width="108" height="112" rx="30" fill="#fff"/><rect x="139" y="76" width="82" height="86" rx="21"/><path d="M151 121h13l10-19 12 34 11-20h12"/><circle cx="241" cy="109" r="4"/>':/hospital|healthcare|home/.test(text)?'<path d="m89 110 91-67 91 67"/><rect x="105" y="108" width="150" height="101" rx="12" fill="#fff"/><rect x="150" y="147" width="60" height="62" rx="8"/><path d="M172 81h16m-8-8v16M123 133h9m96 0h9"/>':'<rect x="103" y="36" width="153" height="174" rx="15" fill="#fff"/><path d="M126 65h70m-70 20h105m-105 21h85M126 170l23-22 23 10 29-34 29 13"/><circle cx="201" cy="124" r="5" fill="#316d78"/>';
 return '<svg viewBox="0 0 360 240" aria-hidden="true"><rect width="360" height="240" rx="16" fill="#eaf1f0"/><circle cx="278" cy="56" r="36" fill="#dae8e5"/><circle cx="69" cy="194" r="50" fill="#dfebe8"/><g stroke="#477d85" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round">'+drawing+'</g></svg>';
}
function hotVisual(i){
 const image=safeUrl(i.image),available=image!=='#';
 return `<figure class="hot-visual">${hotArtwork(i)}${available?`<img src="${esc(image)}" alt="${esc(i.src)}的文章配图" loading="lazy" decoding="async" referrerpolicy="no-referrer">`:''}<figcaption>${available?'来源配图':'主题示意'}</figcaption></figure>`;
}
function renderHot(){
 const rows=hot.slice(0,10);
 $('#hotUpdated').textContent=(Number.isFinite(collected)?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'long',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(collected))+' 更新 · ':'')+'按阅读价值排序';
 $('#hotRows').innerHTML=rows.length?'<div class="hot-podium">'+rows.slice(0,3).map((i,n)=>`<article class="hot-card hot-place-${n+1}"><div class="hot-kicker">${String(n+1).padStart(2,'0')} <span>${esc(i.sourceType)}</span></div><div class="hot-feature-body"><div><h2><a href="${esc(articleHref(i))}">${esc(i.t||i.te)}</a></h2><p class="hot-summary">${esc(excerpt(i,n===0?220:110))}</p></div>${hotVisual(i)}</div><div class="hot-bottom"><div><span>${esc(i.src)}</span><time>原文 ${esc(i.date)}</time></div><div class="hot-number">${score(i)}<small>阅读价值</small></div></div></article>`).join('')+'</div>'+(rows.length>3?'<div class="hot-list-heading">继续看 <span>04—'+String(rows.length).padStart(2,'0')+'</span></div>':'')+'<div class="hot-list">'+rows.slice(3).map((i,n)=>`<article class="hot-row"><span class="hot-order">${String(n+4).padStart(2,'0')}</span><div><h3><a href="${esc(articleHref(i))}">${esc(i.t||i.te)}</a></h3><p>${esc(excerpt(i,120))}</p><span class="meta">${esc(i.src)} · ${esc(i.date)}</span></div><div class="hot-number">${score(i)}<small>阅读价值</small></div></article>`).join('')+'</div>':'<p class="empty">当前暂无符合条件的热点。</p>';
 $('#hotRows').querySelectorAll('.hot-visual img').forEach(img=>img.addEventListener('error',()=>{img.hidden=true;img.parentElement.querySelector('figcaption').textContent='主题示意';},{once:true}));
}

function editorialDetails(i){const e=i.editorial;if(!e?.reviews?.length)return '';const names={significance:'实质份量',novelty:'信息增量',evidence:'证据支持',relevance:'读者相关',usefulness:'可用性'};return `<details class="editorial-details"><summary>评分依据 · 两次评估</summary>${e.reviews.map((r,n)=>`<p>第 ${n+1} 次：${esc(r.total)} 分 · ${Object.entries(r.axes||{}).map(([k,v])=>`${esc(names[k]||k)} ${esc(v)}`).join(' / ')}</p>`).join('')}<p>基于来源提供的摘要；入选门槛 ${esc(e.threshold)} 分。模型：${esc(e.reviews[0].receipt?.model||'')}。</p></details>`;}
function card(i,n,section){const audience=articleAudience(i,section);const reason=i.reasons?.[audience];return `<article class="intel"><div class="meta"><span>${esc(i.src)}</span><span class="pill">${esc(i.sourceType)}</span><time>${esc(i.date)}</time><span class="score-badge" title="两次模型评估的阅读价值；不是临床证据评级">阅读价值 <b>${score(i)}</b></span></div><div class="card-head"><h3><a href="${esc(articleHref(i,audience))}">${esc(i.t||i.te)}</a></h3></div><p class="summary">${esc(excerpt(i))}</p><div class="card-tags">${i.topics.slice(0,2).map(t=>`<span class="pill">${esc(topicNames[t]||t)}</span>`).join('')}${(i.stages||[]).map(t=>`<span class="pill">${esc(stageNames[t]||t)}</span>`).join('')}</div>${reason?`<p class="recommendation"><strong>推荐理由：</strong>${esc(reason)}</p>`:''}${editorialDetails(i)}</article>`;}

function list(el,items){el.innerHTML=items.length?items.map((i,n)=>card(i,n+1)).join(''):'<p class="empty">今日暂无新条目，或没有符合条件的情报。</p>';}
function renderSection(section){
 const category=selectedCategory[section],q=$('#'+section+'Search').value.trim().toLowerCase();
 const extra=section==='research'?$('#researchStage').value:$('#industryScope').value;
 const windowValue=$('#'+section+'Window').value,month=windowValue.startsWith('month:')?windowValue.slice(6):null;
 if(month&&!monthlyData.has(month)){awaitArchive(month,section==='research'?$('#topRows'):$('#industryRows'),()=>renderSection(section));return;}
 const pool=month?monthlyData.get(month).items:windowValue==='history'?[...current,...history]:current;
 const rows=pool.filter(i=>(i.sections||[]).includes(section)&&(category==='all'||(i.categories?.[section]||[]).includes(category))&&
   (extra==='all'||(section==='research'?(i.stages||[]):i.topics).includes(extra))&&
   (!q||(searchText.get(i.id)||[i.t,i.te,i.s,i.se,i.src].join(' ').toLowerCase()).includes(q)));
 const routeName=section==='research'?'jingxuan':'industry';
 $('#'+section+'Tabs').innerHTML=Object.entries(sectionCategories[section]).map(([key,label])=>`<a href="#${routeName}?category=${key}" ${key===category?'aria-current="page"':''}>${label}</a>`).join('');
 const highlights=rows.filter(i=>byId[i.id]&&Number.isFinite(i.rel)).sort((a,b)=>(b.rel||0)-(a.rel||0)).slice(0,5);
 $('#'+section+'Highlights').innerHTML=highlights.length?highlights.map(i=>`<li><a href="${esc(articleHref(i,section))}"><strong>${esc(i.t||i.te)}</strong><span class="highlight-summary">${esc(excerpt(i,100))}</span></a><span class="highlight-score">${score(i)}<small>阅读价值</small></span></li>`).join(''):'<li>当前没有符合条件的内容</li>';
 $('#'+section+'Count').textContent=`${rows.length} 条匹配内容`;
 const groups=new Map();
 [...rows].sort((a,b)=>b.date.localeCompare(a.date)).forEach(i=>{if(!groups.has(i.date))groups.set(i.date,[]);groups.get(i.date).push(i);});
 if(section==='research'){const show=category==='policy';$('#researchHighlights').closest('.highlights').hidden=show;$('#researchSearch').closest('.section-filters').hidden=show;$('#researchWindow').closest('.archive-toolbar').hidden=show;$('#topRows').hidden=show;$('#policyMap').hidden=!show;if(show)renderPolicies();}
 const target=section==='research'?$('#topRows'):$('#industryRows');
 target.innerHTML=rows.length?[...groups].map(([day,items])=>`<section><h2><time>${esc(day)}</time><small>${items.length} 条</small></h2>${items.map((i,n)=>card(i,n+1,section)).join('')}</section>`).join(''):'<p class="empty">当前暂无符合条件的内容。可以切换栏目或清除筛选条件。</p>';
}
for(const section of ['research','industry']){
 for(const month of archiveMonths){const option=document.createElement('option');option.value='month:'+month.month;option.textContent=month.month+' 月度档案';$('#'+section+'Window').append(option);}
 $('#'+section+'Window').addEventListener('change',()=>renderSection(section));
 $('#'+section+'Search').addEventListener('input',()=>renderSection(section));
}
$('#researchStage').addEventListener('change',()=>renderSection('research'));
$('#industryScope').addEventListener('change',()=>renderSection('industry'));
function renderFeed(){const q=$('#search').value.trim().toLowerCase(),topic=$('#topicFilter').value,source=$('#sourceFilter').value;const rows=current.filter(i=>(topic==='all'||i.topics.includes(topic))&&(source==='all'||i.sourceType===source)&&(!q||(searchText.get(i.id)||[i.t,i.te,i.s,i.se,i.src].join(' ').toLowerCase()).includes(q)));list($('#feedRows'),rows);$('#resultCount').textContent=`找到 ${rows.length} 条情报`;}

$('#search').addEventListener('input',renderFeed);$('#topicFilter').addEventListener('change',renderFeed);$('#sourceFilter').addEventListener('change',renderFeed);
const digestLabels={policy:'政策动态',papers:'论文研究',methods:'工具方法',business:'融资合作',regulation:'市场准入',products:'新品方案',technology:'技术进展',overview:'产业动态'};
function digestCategory(i){const cats=Object.values(i.categories||{}).flat();return Object.keys(digestLabels).find(k=>cats.includes(k))||'overview';}
const currentEditions=(D.dailyIssues||[]).map(e=>({...e,item_ids:e.item_ids.filter(id=>byId[id]&&byId[id].date===e.date)})).filter(e=>e.item_ids.length);
const editions=[...currentEditions,...(D.historyIssues||[]).filter(e=>!currentEditions.some(c=>c.date===e.date)).map(e=>({...e,item_ids:e.item_ids.filter(id=>archiveById[id]?.date===e.date)})).filter(e=>e.item_ids.length)].sort((a,b)=>b.date.localeCompare(a.date));
let briefing='';
function allEditions(){
 const map=new Map(editions.map(e=>[e.date,{...e,headline:archiveById[e.item_ids[0]]?.t||archiveById[e.item_ids[0]]?.te,count:e.item_ids.length}]));
 for(const month of archiveMonths)for(const e of monthlyData.get(month.month)?.editions||month.editions)map.set(e.date,{...e,archiveMonth:month.month,count:e.count??e.item_ids?.length});
 return [...map.values()].sort((a,b)=>b.date.localeCompare(a.date));
}
function dailyCalendar(dateValue,catalog,publication){
 const [year,month,day]=dateValue.split('-').map(Number),first=new Date(Date.UTC(year,month-1,1)),days=new Date(Date.UTC(year,month,0)).getUTCDate();
 const prefix=dateValue.slice(0,7),available=new Set(catalog.filter(e=>e.date.startsWith(prefix)).map(e=>e.date));if(publication?.date.startsWith(prefix))available.add(publication.date);
 const weeks=['一','二','三','四','五','六','日'],weekday=weeks[(new Date(dateValue+'T00:00:00Z').getUTCDay()+6)%7];
 const cells=Array.from({length:(first.getUTCDay()+6)%7},()=>'<span class="calendar-gap"></span>');
 for(let n=1;n<=days;n++){const key=prefix+'-'+String(n).padStart(2,'0');cells.push(available.has(key)?`<a href="#daily?date=${key===publication?.date?'today':key}" aria-label="${key} 日报" ${n===day?'aria-current="date"':''}><span aria-hidden="true"></span></a>`:`<span class="calendar-empty" aria-label="${key} 未收录日报" title="${n} 日 · 未收录日报"></span>`);}
 return `<div class="calendar-stamp"><small>阅读档案</small><strong>${String(day).padStart(2,'0')}</strong><span>${year} 年 ${month} 月</span><span>星期${weekday}</span></div><div class="calendar-month"><header><b>${month} 月</b><span>本月 ${available.size} 期</span></header><div class="calendar-week">${weeks.map(w=>'<span>'+w+'</span>').join('')}</div><div class="calendar-grid">${cells.join('')}</div></div>`;
}
function renderDaily(requested){
 const publication=D.publicationIssue?.date===today?D.publicationIssue:null,catalog=allEditions();
 const selected=requested||(publication?'today':catalog[0]?.date);
 const edition=selected==='today'?publication:catalog.find(e=>e.date===selected);
 const isPublication=edition===publication&&!!publication;
 const selectedDate=edition?.date||(/^\d{4}-\d{2}-\d{2}$/.test(selected||'')?selected:today);
 const groups=new Map();for(const e of catalog){const month=e.date.slice(0,7);if(!groups.has(month))groups.set(month,[]);groups.get(month).push(e);}
 $('#dailyDates').innerHTML=(publication?`<a class="today-edition" href="#daily?date=today" ${isPublication?'aria-current="page"':''}><time>${esc(publication.date.slice(8))}</time><span>今日要闻<small>${publication.item_ids.length} 篇精选</small></span></a>`:'')+[...groups].map(([month,rows])=>`<details class="digest-month" ${selectedDate.startsWith(month)?'open':''}><summary>${esc(month.replace('-',' 年 '))} 月 <span>${rows.length}</span></summary>${rows.map(e=>`<a href="#daily?date=${esc(e.date)}" ${e.date===selected?'aria-current="page"':''}><time datetime="${esc(e.date)}">${esc(e.date.slice(8))}</time><span>${esc(e.headline||'历史日报')}<small>${e.archiveMonth?'回溯整理 · ':''}${e.count} 条</small></span></a>`).join('')}</details>`).join('')||'<p class="digest-no-dates">暂无日报</p>';
 $('#dailyDateSelect').innerHTML=(publication?`<option value="today">${esc(publication.date)} · 今日出刊</option>`:'')+catalog.map(e=>`<option value="${esc(e.date)}">${esc(e.date)} · ${e.count} 件大事${e.archiveMonth?' · 回溯':''}</option>`).join('');
 $('#dailyDateSelect').value=isPublication?'today':edition?edition.date:'';$('#dailyDateSelect').disabled=!catalog.length&&!publication;
 $('#dailyCalendar').innerHTML=dailyCalendar(selectedDate,catalog,publication);
 $('#dailyDate').textContent=selectedDate.replaceAll('-','.');
 const month=edition?.archiveMonth;
 $('#monthlyLinks').innerHTML=month?`<p>本月资料按原文日期回溯整理，未收录的日期不补写日报。</p><div class="actions"><a href="#jingxuan?month=${month}" class="text-link">浏览本月科研资料 →</a><a href="#industry?month=${month}" class="text-link">浏览本月产业资料 →</a><a href="archive/${month}/daily.md" download class="text-link">下载日报合订本 ↓</a><a href="archive/${month}/records.json" download class="text-link">原始记录 ↓</a></div>`:'';
 if(month&&!monthlyData.has(month)){$('#dailyTitle').textContent='历史日报';$('#dailyMeta').textContent='正在载入';$('#dailyUpdate').textContent='按原文日期回溯整理，不代表当日实际出刊。';$('#copyBtn').disabled=true;awaitArchive(month,$('#dailyStories'),()=>renderDaily(requested));return;}
 const source=month?Object.fromEntries(monthlyData.get(month).items.map(i=>[i.id,i])):archiveById;
 const rows=edition?(edition.item_ids||[]).map(id=>source[id]).filter(Boolean):[];
 $('#dailyTitle').textContent=rows.length?`${isPublication?'今日阅读 ·':month?'历史回溯 ·':'这一天的'} ${rows.length} 件 AI 医疗大事`:'这一天暂无已收录要闻';
 $('#dailyUpdate').textContent=month?'按原文日期回溯整理，不代表当日实际出刊。':'更新于 '+(Number.isFinite(collected)?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'short',timeStyle:'short'}).format(new Date(collected)):'未知')+'（北京时间）'+(isPublication?' · 本期选自近三日原文，每篇保留原始发布日期。':' · 按原文发布日期归档。');
 $('#dailyMeta').innerHTML=rows.length?`<span><b>${rows.length}</b> 件大事</span><span><b>${new Set(rows.map(i=>i.src)).size}</b> 个来源</span><span class="digest-minutes">约 ${edition.minutes} 分钟读完</span>`:'有值得关注的新进展时，会整理在这里。';
 $('#dailyStories').innerHTML=rows.map((i,n)=>`<article class="digest-story"><span class="digest-number">${String(n+1).padStart(2,'0')}</span><div><p class="digest-category">${esc(digestLabels[digestCategory(i)])}</p><h2><a href="${esc(articleHref(i))}">${esc(i.t||i.te)}</a></h2><p class="digest-summary">${esc(excerpt(i,360))}</p><div class="digest-source"><span>${esc(i.src)}</span><time>原文 ${esc(i.date)}</time><a href="${esc(safeUrl(i.u))}" target="_blank" rel="noopener noreferrer">原文 ↗</a></div></div></article>`).join('');
 briefing=rows.length?`奇点医研 · 奇点日报 · ${edition.date}\n${month?'历史回溯整理 · ':''}${rows.length} 件 AI 医疗大事\n\n`+rows.map((i,n)=>`${String(n+1).padStart(2,'0')} · ${digestLabels[digestCategory(i)]}\n${i.t||i.te}\n${i.s||i.se||'来源未提供摘要，请阅读原文。'}\n${i.src} · ${i.date}\n${safeUrl(i.u)}\n`).join('\n'):'这一天暂无已收录条目。';
 if(isPublication)briefing=publication.text;
 $('#copyBtn').disabled=!rows.length;
}
$('#dailyDateSelect').onchange=e=>{location.hash='daily?date='+e.target.value;};
$('#copyBtn').onclick=()=>copy(briefing,'日报已复制');$('#copyWechat').onclick=()=>copy('13028564458','微信号已复制，请到微信搜索添加');

function renderPolicies(){
 const region=$('#policyRegion').value;
 const rows=(D.policyTimeline?.items||[]).filter(i=>region==='all'||(region==='pilot'?i.pilot:i.country===region)).sort((a,b)=>a.date.localeCompare(b.date));
 $('#policyRows').innerHTML=['中国','美国'].map((country,index)=>{
  const nodes=rows.filter(i=>i.country===country);if(!nodes.length)return '';
  return `<section class="policy-lane" data-country="${country}"><header class="policy-lane-header"><h2 id="policy-country-${index}">${country}<small>${nodes.length} 个政策节点</small></h2><p>早期 → 近期 · 左右滑动</p></header><div class="policy-scroll" role="region" tabindex="0" aria-labelledby="policy-country-${index}"><ol class="policy-track">${nodes.map(i=>`<li class="policy-stop"><a class="policy-node" href="${esc(safeUrl(i.url))}" target="_blank" rel="noopener noreferrer" aria-label="${esc(i.date+' '+i.title+'，打开官方原文')}"><time datetime="${esc(i.date)}">${esc(i.date)}</time><div class="policy-node-body"><span class="pill">${esc(i.kind)}</span><h3>${esc(i.title)}</h3><p class="policy-change">${esc(i.change)}</p><span class="policy-open">${esc(i.source)} · 原文 ↗</span></div></a><details class="policy-detail"><summary>政策解读与适用边界</summary><p><strong>对你意味着什么 · 编辑解读：</strong>${esc(i.meaning)}</p><p>${esc(i.boundary)}</p>${i.date_note?`<p>${esc(i.date_note)}</p>`:''}</details></li>`).join('')}</ol></div></section>`;
 }).join('')||'<p class="empty">暂无相关节点</p>';
}
$('#policyRegion').addEventListener('change',renderPolicies);
if(today>='2026-10-05'){$('#groupCode').hidden=true;$('#groupDownload').hidden=true;$('#groupExpiry').textContent='本期入群二维码已过期，请添加下方微信获取新的入群方式。';}

const themeQuery=window.matchMedia?window.matchMedia('(prefers-color-scheme: dark)'):null;
function applyTheme(mode){
 document.documentElement.dataset.themeMode=mode;
 const dark=mode==='dark'||(mode==='system'&&themeQuery?.matches);
 document.documentElement.dataset.theme=dark?'dark':'light';
 document.querySelector('meta[name="theme-color"]').content=dark?'#171d1f':'#f7f8f5';
 document.querySelectorAll('[data-theme-choice]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.themeChoice===mode)));
 document.querySelectorAll('.theme-caption').forEach(el=>el.textContent={dark:'深色模式',light:'浅色模式',system:'跟随系统'}[mode]);
}
for(const b of document.querySelectorAll('[data-theme-choice]'))b.onclick=()=>{const mode=b.dataset.themeChoice;try{localStorage.setItem('sih-theme',mode);}catch{}applyTheme(mode);};
themeQuery?.addEventListener('change',()=>{if(document.documentElement.dataset.themeMode==='system')applyTheme('system');});
applyTheme(document.documentElement.dataset.themeMode||'system');
const base='https://zhangminton731-a11y.github.io/ai-health-intel/';
$('#rssUrl').textContent=base+'feed.xml';$('#copyRss').onclick=()=>copy(base+'feed.xml','RSS 地址已复制');
$('#accessFreshness').textContent='数据截至 '+D.asOf;
$('#connectPreviewHint').hidden=!(location.protocol==='file:'||['localhost','127.0.0.1'].includes(location.hostname));
$('#skillPrompt').textContent=`请从 ${base}sih-intel.zip 下载奇点医研 Skill，先检查文件，再按照当前客户端的技能安装规则安装。已有同名技能时先比较差异并保留旧版本，不直接覆盖。安装后告知是否需要新开会话，再读取来源健康并返回医学科研精选最多 5 条，附日期、来源和原文；不足则如实说明。`;
$('#mcpConfig').textContent=JSON.stringify({mcpServers:{'sih-intel':{command:'/absolute/path/to/.venv/bin/python',args:['/absolute/path/to/sih-mcp/server.py']}}},null,2);
$('#apiUrls').textContent=['health','items','briefing'].map(x=>'GET '+base+'api/v1/'+x+'.json').join('\n');
$('#apiExample').textContent='curl "'+base+'api/v1/health.json"\ncurl "'+base+'api/v1/items.json"';
for(const button of document.querySelectorAll('[data-copy-target],[data-copy-value]'))button.onclick=()=>copy(button.dataset.copyValue||document.getElementById(button.dataset.copyTarget).textContent,'已复制');
function showAccess(tab){if(!['skill','mcp','rss','api'].includes(tab))tab='skill';document.querySelectorAll('.access-panel').forEach(p=>p.hidden=p.id!=='access-'+tab);document.querySelectorAll('[data-access-tab]').forEach(a=>{if(a.dataset.accessTab===tab)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});}
let screenshotUrl='',screenshotName='';
function feedbackChanged(){$('#feedbackCount').textContent=$('#feedbackText').value.length+' / 2000';$('#copyFeedback').disabled=!$('#feedbackText').value.trim()||$('#feedbackText').value.length>2000||!$('#feedbackEmail').checkValidity();$('#feedbackStatus').textContent='';}
$('#feedbackText').addEventListener('input',feedbackChanged);$('#feedbackEmail').addEventListener('input',feedbackChanged);
function removeScreenshot(){if(screenshotUrl)URL.revokeObjectURL(screenshotUrl);screenshotUrl='';screenshotName='';$('#previewImage').removeAttribute('src');$('#imagePreview').hidden=true;$('#feedbackImage').value='';$('#imageName').textContent='';}
function setScreenshot(file){
 removeScreenshot();$('#feedbackError').textContent='';if(!file)return;
 if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>5*1024*1024||file.size===0){$('#feedbackError').textContent='请选择不超过 5 MB 的 PNG、JPEG 或 WebP 图片。';return;}
 screenshotUrl=URL.createObjectURL(file);screenshotName=file.name;$('#previewImage').src=screenshotUrl;$('#imageName').textContent=file.name;$('#imagePreview').hidden=false;
}
$('#previewImage').onerror=()=>{removeScreenshot();$('#feedbackError').textContent='图片无法读取，请换一张有效截图。';};
$('#feedbackImage').addEventListener('change',e=>setScreenshot(e.target.files[0]));$('#removeImage').onclick=()=>{removeScreenshot();$('#feedbackError').textContent='';};
$('#imageDrop').addEventListener('dragover',e=>e.preventDefault());$('#imageDrop').addEventListener('drop',e=>{e.preventDefault();setScreenshot(e.dataTransfer.files[0]);});
$('#feedbackForm').addEventListener('paste',e=>{const item=[...(e.clipboardData?.items||[])].find(x=>x.kind==='file');if(item){e.preventDefault();setScreenshot(item.getAsFile());}});
$('#feedbackForm').addEventListener('submit',async e=>{
 e.preventDefault();feedbackChanged();if($('#copyFeedback').disabled){$('#feedbackError').textContent='请填写 1–2000 字反馈，并检查选填邮箱格式。';return;}
 const body=['【奇点医研网站反馈】',$('#feedbackText').value.trim(),$('#feedbackEmail').value?'联系邮箱：'+$('#feedbackEmail').value:'',screenshotName?'截图：'+screenshotName+'（请在微信中另行添加）':'','网站：'+base].filter(Boolean).join('\n\n');
 const ok=await copy(body,'反馈已复制，请到微信发送');$('#feedbackStatus').textContent=ok?'反馈已复制，尚未发送。请粘贴到与商务微信 13028564458 的聊天中，截图另行添加。':'复制未成功，请手动选择反馈文字，再到微信发送。';
});
window.addEventListener('pagehide',removeScreenshot);
$('#shareBtn').onclick=async()=>{if(navigator.share){try{await navigator.share({title:'奇点医研 · AI 健康产业情报',url:base});}catch(e){if(e.name!=='AbortError')copy(base,'网站链接已复制');}}else copy(base,'网站链接已复制');};
let riverLoading=false;
function renderAbout(){
 const sources=(D.srcs||[]).filter(s=>s.status!=='inactive');
 $('#aboutSourceCount').textContent=sources.length;
 const publication=D.publicationIssue;
 const dailyCount=publication&&publication.date===today?(publication.item_ids||[]).filter(id=>current.some(i=>i.id===id)).length:0;
 const metrics=[['采集',sources.length,'个启用信源','持续关注论文、机构与产业发布，从源头找到值得阅读的进展。'],['收录',D.nItems??D.items.length,'条本批记录','记录来源与原文日期，规范内容、去重后进入资料池。'],['精选',current.length,'条当前推荐','模型独立评估两次，按实质份量、信息增量、证据支持、读者相关性和可用性筛选。'],['成刊',dailyCount,'条今日要闻','从当前推荐生成奇点日报，也可通过 RSS、API、MCP 和 Skill 读取。']];
 $('#aboutMetrics').innerHTML=metrics.map(([label,value,unit,note],i)=>`<article><div class="metric-stage"><span>0${i+1}</span>${label}</div><div class="metric-value"><strong>${value.toLocaleString('zh-CN')}</strong><small>${unit}</small></div><p>${note}</p></article>`).join('');
 $('#aboutSnapshot').textContent=`数据快照 · ${D.generatedAt?new Date(D.generatedAt).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):D.asOf}（北京时间）；收录为本批记录，非历史累计。`;
 $('#aboutSources').innerHTML=sources.map(s=>`<article class="source-card"><h3>${esc(s.name)}</h3><p>${esc(s.role||'公开信息来源')}</p><small>${Number(s.n)||0} 条本批记录</small></article>`).join('')||'<p class="muted">暂无信源目录</p>';
 const latest=[...current].sort((a,b)=>b.date.localeCompare(a.date))[0];
 $('#riverLatest').innerHTML=latest?`<small>最近推荐</small><a href="${articleHref(latest)}">${esc(latest.t||latest.te)}</a><span>${esc(latest.src)}</span>`:'<small>等待新的推荐</small>';
 if(window.SihSignalRiver){window.SihSignalRiver.mount($('#signalRiver'),sources);return;}
 if(!riverLoading){riverLoading=true;const script=document.createElement('script');script.src='assets/signal-river.bfd40536503985fc.js';script.onload=()=>{if($('#v-about').classList.contains('active'))window.SihSignalRiver?.mount($('#signalRiver'),sources);};script.onerror=()=>{riverLoading=false;script.remove();};document.head.append(script);}
}
function route(){const parts=(location.hash.slice(1)||'jingxuan').split('?');let v=parts[0]==='policy'?'jingxuan':parts[0];if(!document.getElementById('v-'+v))v='jingxuan';document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id==='v-'+v));document.querySelectorAll('.nav-link,.mobile-nav a').forEach(a=>{if(a.getAttribute('href')===(a.closest('.mobile-nav')&&['more','connect','about','feedback'].includes(v)?'#more':'#'+v))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});if(v==='feed'){const topic=new URLSearchParams(parts[1]||'').get('topic');if(topic&&topicNames[topic])$('#topicFilter').value=topic;renderFeed();}if(v==='jingxuan'||v==='industry'){const section=v==='jingxuan'?'research':'industry';const archiveMonth=new URLSearchParams(parts[1]||'').get('month');if(archiveMonths.some(m=>m.month===archiveMonth))$('#'+section+'Window').value='month:'+archiveMonth;const category=parts[0]==='policy'?'policy':new URLSearchParams(parts[1]||'').get('category')||'all';selectedCategory[section]=Object.hasOwn(sectionCategories[section],category)?category:'all';renderSection(section);}if(v==='about')renderAbout();else window.SihSignalRiver?.stop();if(v==='hot')renderHot();if(v==='article')renderArticle(new URLSearchParams(parts[1]||''));if(v==='daily')renderDaily(new URLSearchParams(parts[1]||'').get('date'));if(v==='connect')showAccess(new URLSearchParams(parts[1]||'').get('tab')||'skill');if(new URLSearchParams(parts[1]||'').get('list')==='1'&&(v==='jingxuan'||v==='industry')){const el=v==='jingxuan'?$('#topRows'):$('#industryRows');el.scrollIntoView?.({block:'start'});}else window.scrollTo(0,0);}
window.addEventListener('hashchange',route);route();
})();