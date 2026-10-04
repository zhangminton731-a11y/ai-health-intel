(()=>{
'use strict';
const D=JSON.parse(document.getElementById('payload').textContent);
const $=s=>document.querySelector(s);
const topicNames={hospital:'医院端 AI',consumer:'消费健康',research:'研究证据',business:'商业动态',regulation:'监管进展'};
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
else if(D.statusRaw!=='complete')warning='本批部分来源暂不可用，内容覆盖可能不完整。';
if(warning){$('#staleNotice').textContent=warning;$('#staleNotice').hidden=false;}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').hidden=true,3200);}
async function copy(value,message){try{await navigator.clipboard.writeText(value);toast(message);return true;}catch{toast('复制未成功，请长按选中页面文字复制。');return false;}}
function articleAudience(i,section){return ['research','industry'].includes(section)&&(i.sections||[]).includes(section)?section:(i.sections||[]).includes('research')?'research':'industry';}
function articleHref(i,section){return '#article?'+new URLSearchParams({id:i.id,section:articleAudience(i,section)});}
function renderArticle(params){
 const id=params.get('id'),i=Object.hasOwn(archiveById,id)?archiveById[id]:null;
 if(!i){$('#articleReader').innerHTML='<a class="text-link" href="#jingxuan">← 返回医学科研</a><h1>这篇内容暂不可用</h1><p class="muted">请返回信息流查看当前收录的内容。</p>';return;}
 const audience=articleAudience(i,params.get('section')),home=audience==='research'?'jingxuan':'industry',reason=i.reasons?.[audience],url=safeUrl(i.u);
 $('#articleReader').innerHTML=`<a class="text-link" href="#${home}">← 返回${audience==='research'?'医学科研':'产业前沿'}</a><h1>${esc(i.t||i.te)}</h1><div class="meta"><span>${esc(i.src)}</span><span class="pill">${esc(i.sourceType)}</span><time>${esc(i.date)}</time></div>${reason?`<section class="reader-reason"><h2>推荐理由</h2><p>${esc(reason)}</p></section>`:''}<section class="reader-summary"><h2>内容摘要</h2><p>${esc(i.s||i.se||'来源未提供摘要，请前往来源阅读。')}</p></section><div class="reader-source">${url!=='#'?`<a class="button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">前往来源阅读全文 ↗</a>`:'<p class="muted">原文链接暂不可用。</p>'}</div>`;
 document.querySelectorAll(`.nav-link[href="#${home}"],.mobile-nav a[href="#${home}"]`).forEach(a=>a.setAttribute('aria-current','page'));
}
function card(i,n,section){const audience=articleAudience(i,section);const reason=i.reasons?.[audience];return `<article class="intel"><div class="meta"><span>${esc(i.src)}</span><span class="pill">${esc(i.sourceType)}</span><time>${esc(i.date)}</time></div><div class="card-head"><h3><a href="${esc(articleHref(i,audience))}">${esc(i.t||i.te)}</a></h3></div><p class="summary">${esc(i.s||i.se||'来源未提供摘要，请阅读原文。')}</p><div class="card-tags">${i.topics.slice(0,2).map(t=>`<span class="pill">${esc(topicNames[t]||t)}</span>`).join('')}${(i.stages||[]).map(t=>`<span class="pill">${esc(stageNames[t]||t)}</span>`).join('')}</div>${reason?`<p class="recommendation"><strong>推荐理由：</strong>${esc(reason)}</p>`:''}</article>`;}

function list(el,items){el.innerHTML=items.length?items.map((i,n)=>card(i,n+1)).join(''):'<p class="empty">今日暂无新条目，或没有符合条件的情报。</p>';}
function renderSection(section){
 const category=selectedCategory[section],q=$('#'+section+'Search').value.trim().toLowerCase();
 const extra=section==='research'?$('#researchStage').value:$('#industryScope').value;
 const pool=$('#'+section+'Window').value==='history'?[...current,...history]:current;
 const rows=pool.filter(i=>(i.sections||[]).includes(section)&&(category==='all'||(i.categories?.[section]||[]).includes(category))&&
   (extra==='all'||(section==='research'?(i.stages||[]):i.topics).includes(extra))&&
   (!q||searchText.get(i.id).includes(q)));
 const routeName=section==='research'?'jingxuan':'industry';
 $('#'+section+'Tabs').innerHTML=Object.entries(sectionCategories[section]).map(([key,label])=>`<a href="#${routeName}?category=${key}" ${key===category?'aria-current="page"':''}>${label}</a>`).join('');
 const highlights=rows.filter(i=>byId[i.id]).sort((a,b)=>(b.rel||0)-(a.rel||0)).slice(0,5);
 $('#'+section+'Highlights').innerHTML=highlights.length?highlights.map(i=>`<li><a href="${esc(articleHref(i,section))}">${esc(i.t||i.te)}</a></li>`).join(''):'<li>当前没有符合条件的内容</li>';
 $('#'+section+'Count').textContent=`${rows.length} 条匹配内容`;
 const groups=new Map();
 [...rows].sort((a,b)=>b.date.localeCompare(a.date)).forEach(i=>{if(!groups.has(i.date))groups.set(i.date,[]);groups.get(i.date).push(i);});
 if(section==='research'){const show=category==='policy';$('#researchHighlights').closest('.highlights').hidden=show;$('#researchSearch').closest('.section-filters').hidden=show;$('#researchWindow').closest('.archive-toolbar').hidden=show;$('#topRows').hidden=show;$('#policyMap').hidden=!show;if(show)renderPolicies();}
 const target=section==='research'?$('#topRows'):$('#industryRows');
 target.innerHTML=rows.length?[...groups].map(([day,items])=>`<section><h2><time>${esc(day)}</time><small>${items.length} 条</small></h2>${items.map((i,n)=>card(i,n+1,section)).join('')}</section>`).join(''):'<p class="empty">当前暂无符合条件的内容。可以切换栏目或清除筛选条件。</p>';
}
for(const section of ['research','industry']){
 $('#'+section+'Window').addEventListener('change',()=>renderSection(section));
 $('#'+section+'Search').addEventListener('input',()=>renderSection(section));
}
$('#researchStage').addEventListener('change',()=>renderSection('research'));
$('#industryScope').addEventListener('change',()=>renderSection('industry'));
function renderFeed(){const q=$('#search').value.trim().toLowerCase(),topic=$('#topicFilter').value,source=$('#sourceFilter').value;const rows=current.filter(i=>(topic==='all'||i.topics.includes(topic))&&(source==='all'||i.sourceType===source)&&(!q||searchText.get(i.id).includes(q)));list($('#feedRows'),rows);$('#resultCount').textContent=`找到 ${rows.length} 条情报`;}

$('#search').addEventListener('input',renderFeed);$('#topicFilter').addEventListener('change',renderFeed);$('#sourceFilter').addEventListener('change',renderFeed);
$('#kws').innerHTML=D.kws.map(k=>`<span class="pill">${esc(k.term)} · ${k.n}</span>`).join('');
const digestLabels={policy:'政策动态',papers:'论文研究',methods:'工具方法',business:'融资合作',regulation:'市场准入',products:'新品方案',technology:'技术进展',overview:'产业动态'};
function digestCategory(i){const cats=Object.values(i.categories||{}).flat();return Object.keys(digestLabels).find(k=>cats.includes(k))||'overview';}
const currentEditions=(D.dailyIssues||[]).map(e=>({...e,item_ids:e.item_ids.filter(id=>byId[id]&&byId[id].date===e.date)})).filter(e=>e.item_ids.length);
const editions=[...currentEditions,...(D.historyIssues||[]).filter(e=>!currentEditions.some(c=>c.date===e.date)).map(e=>({...e,item_ids:e.item_ids.filter(id=>archiveById[id]?.date===e.date)})).filter(e=>e.item_ids.length)].sort((a,b)=>b.date.localeCompare(a.date));
let briefing='';
function renderDaily(requested){
 const selected=requested||editions[0]?.date;
 const edition=editions.find(e=>e.date===selected);
 const rows=edition?edition.item_ids.map(id=>archiveById[id]):[];
 $('#dailyDates').innerHTML=editions.map(e=>`<a href="#daily?date=${esc(e.date)}" ${e.date===selected?'aria-current="page"':''}><time datetime="${esc(e.date)}">${esc(e.date.slice(5).replace('-','月'))}日</time><span>${esc(archiveById[e.item_ids[0]].t||archiveById[e.item_ids[0]].te)}</span></a>`).join('')||'<p class="digest-no-dates">暂无日报</p>';
 $('#dailyDateSelect').innerHTML=editions.map(e=>`<option value="${esc(e.date)}">${esc(e.date)} · ${e.item_ids.length} 件大事</option>`).join('');
 $('#dailyDateSelect').value=edition?edition.date:'';$('#dailyDateSelect').disabled=!editions.length;
 $('#dailyDate').textContent=edition?edition.date.replaceAll('-','.'):'';
 $('#dailyTitle').textContent=rows.length?`这一天的 ${rows.length} 件 AI 医疗大事`:'这一天，暂无精选';
 $('#dailyUpdate').textContent='最近采集：'+(Number.isFinite(collected)?new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'short',timeStyle:'short'}).format(new Date(collected)):'未知')+'（北京时间） · 最新有内容日报：'+(editions[0]?.date||'暂无')+(D.coverage?.dates?.[0]?' · '+D.asOf+' 原文：收录 '+D.coverage.dates[0].collected+' 条，入选 '+D.coverage.dates[0].selected+' 条':'')+'。日报按原文日期归集。';
 $('#dailyMeta').textContent=rows.length?`${rows.length} 条核心资讯 · 约 ${edition.minutes} 分钟`:'有值得关注的新进展时，会整理在这里。';
 $('#dailyStories').innerHTML=rows.map((i,n)=>`<article class="digest-story"><span class="digest-number">${String(n+1).padStart(2,'0')}</span><div><p class="digest-category">${esc(digestLabels[digestCategory(i)])}</p><h2><a href="${esc(articleHref(i))}">${esc(i.t||i.te)}</a></h2><p class="digest-summary">${esc(i.s||i.se||'来源未提供摘要，请阅读原文。')}</p><div class="digest-source"><span>${esc(i.src)}</span><a href="${esc(safeUrl(i.u))}" target="_blank" rel="noopener noreferrer">原文 ↗</a></div></div></article>`).join('');
 briefing=rows.length?`奇点医研 · 奇点日报 · ${edition.date}\n这一天的 ${rows.length} 件 AI 医疗大事\n\n`+rows.map((i,n)=>`${String(n+1).padStart(2,'0')} · ${digestLabels[digestCategory(i)]}\n${i.t||i.te}\n${i.s||i.se||'来源未提供摘要，请阅读原文。'}\n${i.src} · ${i.date}\n${safeUrl(i.u)}\n`).join('\n'):'今日暂无新条目，请稍后再来。';
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
function route(){const parts=(location.hash.slice(1)||'jingxuan').split('?');let v=parts[0]==='policy'?'jingxuan':parts[0];if(!document.getElementById('v-'+v))v='jingxuan';document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id==='v-'+v));document.querySelectorAll('.nav-link,.mobile-nav a').forEach(a=>{if(a.getAttribute('href')===(a.closest('.mobile-nav')&&['more','connect','about','feedback'].includes(v)?'#more':'#'+v))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});if(v==='feed'){const topic=new URLSearchParams(parts[1]||'').get('topic');if(topic&&topicNames[topic])$('#topicFilter').value=topic;renderFeed();}if(v==='jingxuan'||v==='industry'){const section=v==='jingxuan'?'research':'industry';const category=parts[0]==='policy'?'policy':new URLSearchParams(parts[1]||'').get('category')||'all';selectedCategory[section]=Object.hasOwn(sectionCategories[section],category)?category:'all';renderSection(section);}if(v==='hot')list($('#hotRows'),hot);if(v==='article')renderArticle(new URLSearchParams(parts[1]||''));if(v==='daily')renderDaily(new URLSearchParams(parts[1]||'').get('date'));if(v==='connect')showAccess(new URLSearchParams(parts[1]||'').get('tab')||'skill');if(new URLSearchParams(parts[1]||'').get('list')==='1'&&(v==='jingxuan'||v==='industry')){const el=v==='jingxuan'?$('#topRows'):$('#industryRows');el.scrollIntoView?.({block:'start'});}else window.scrollTo(0,0);}
window.addEventListener('hashchange',route);route();
})();