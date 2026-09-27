const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM,VirtualConsole}=require('jsdom');
const template=fs.readFileSync('templates/site.html','utf8');
const stamp=new Date().toISOString();
const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
function entry(id,title,topics){return {id,t:title,te:title,s:'来源摘要',se:'summary',u:'https://example.org/'+id,src:'Test journal',sourceType:'期刊论文',topics,date:day,freshness:'fresh',tier:'skim',event:'new'};}
function page(change={}){
 const items=[entry('hospital','Hospital imaging AI',['hospital','research']),entry('ring','Wearable smart ring',['consumer'])];
 const payload={name:'健微知著',asOf:day,generatedAt:stamp,statusRaw:'complete',nSrc:12,items,top:items.map(i=>i.id),hot30:items,kws:[],srcs:[],briefing:'同一份简报',...change};
 const writes=[],errors=[];
 const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
 const html=template.replace('__PAYLOAD__',JSON.stringify(payload).replaceAll('</','<\\/'));
 const dom=new JSDOM(html,{url:'https://example.org/ai-health-intel/',runScripts:'dangerously',virtualConsole:vc,beforeParse(window){window.scrollTo=()=>{};Object.defineProperty(window.navigator,'clipboard',{value:{writeText:async text=>writes.push(text)}});}});
 return {dom,doc:dom.window.document,writes,errors};
}
test('initial render has full titles, same briefing, no JS errors',()=>{const p=page();assert.equal(p.errors.length,0);assert.equal(p.doc.querySelectorAll('#topRows article').length,2);assert.equal(p.doc.querySelector('#dailyText').textContent,'同一份简报');assert(!p.doc.body.textContent.includes('未经人工审核'));p.dom.window.close();});
test('keyword and topic filters operate together',()=>{const p=page();const w=p.dom.window;const topic=p.doc.querySelector('#topicFilter');topic.value='consumer';topic.dispatchEvent(new w.Event('change'));assert.equal(p.doc.querySelectorAll('#feedRows article').length,1);const search=p.doc.querySelector('#search');search.value='no match';search.dispatchEvent(new w.Event('input'));assert.equal(p.doc.querySelectorAll('#feedRows article').length,0);p.dom.window.close();});
test('mobile navigation opens cooperation and copies the authorized WeChat',async()=>{const p=page();const w=p.dom.window;w.location.hash='#about';w.dispatchEvent(new w.HashChangeEvent('hashchange'));assert(p.doc.querySelector('#v-about').classList.contains('active'));p.doc.querySelector('#copyWechat').click();await Promise.resolve();assert.deepEqual(p.writes,['13028564458']);p.dom.window.close();});
test('source text is escaped and javascript links are rejected',()=>{const evil=entry('evil','<img src=x onerror=alert(1)>',['hospital']);evil.u='javascript:alert(1)';const p=page({items:[evil],top:['evil'],hot30:[evil]});assert.equal(p.doc.querySelectorAll('#topRows img').length,0);assert.equal(p.doc.querySelector('#topRows h3 a').getAttribute('href'),'#');assert.equal(p.errors.length,0);p.dom.window.close();});
test('a frozen old page expires recommendations and displays an update warning',()=>{const item=entry('old','Expired headline',['hospital']);item.date='2020-01-01';const p=page({generatedAt:'2020-01-01T00:00:00Z',asOf:'2020-01-01',items:[item],top:['old'],hot30:[item]});assert.equal(p.doc.querySelectorAll('#topRows article').length,0);assert.equal(p.doc.querySelector('#staleNotice').hidden,false);assert(!p.doc.querySelector('#dailyText').textContent.includes('Expired headline'));p.dom.window.close();});
test('unknown route recovers to home',()=>{const p=page();p.dom.window.location.hash='#unknown';p.dom.window.dispatchEvent(new p.dom.window.HashChangeEvent('hashchange'));assert(p.doc.querySelector('#v-jingxuan').classList.contains('active'));p.dom.window.close();});
test('clipboard refusal displays actionable fallback',async()=>{const p=page();p.dom.window.navigator.clipboard.writeText=async()=>{throw Error('denied');};p.doc.querySelector('#copyWechat').click();await new Promise(resolve=>setImmediate(resolve));assert.match(p.doc.querySelector('#toast').textContent,/长按/);p.dom.window.close();});
