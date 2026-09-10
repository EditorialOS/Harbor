"""Portable MCP Apps UI for Harbor's authenticated intelligence workspace."""

HARBOR_APP_URI = "ui://harbor/intelligence-summary-v3.html"

HARBOR_APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root { color-scheme: light; --ink:#111; --muted:#707070; --soft:#f4f4f4; --line:#e7e7e7; --paper:#fff; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--paper); color:var(--ink); font:14px/1.45 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    button,select { font:inherit; color:inherit; }
    .shell { background:#fff; }
    .masthead { display:flex; justify-content:space-between; align-items:center; padding:20px 28px; border-bottom:1px solid var(--line); }
    .product { font-size:15px; font-weight:650; }
    .status { display:flex; align-items:center; gap:7px; color:var(--muted); font-size:13px; }
    .dot { width:7px; height:7px; border-radius:50%; background:var(--ink); }
    .controls { padding:20px 28px; border-bottom:1px solid var(--line); }
    .periods { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; }
    .period { border:0; background:transparent; border-radius:999px; padding:6px 10px; color:var(--muted); cursor:pointer; }
    .period:hover,.period:focus-visible { background:var(--soft); color:var(--ink); outline:none; }
    .period.active { background:var(--ink); color:#fff; }
    .selection { display:flex; align-items:center; justify-content:space-between; gap:12px; }
    .selection-label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.07em; }
    select { max-width:65%; border:0; background:transparent; text-align:right; cursor:pointer; outline:none; }
    .report { padding:26px 28px; border-bottom:1px solid var(--line); }
    .report-heading { display:flex; flex-wrap:wrap; gap:.28em; font-size:24px; line-height:1.25; font-weight:400; letter-spacing:-.015em; }
    .report-date { color:var(--muted); }
    .metrics { display:grid; grid-template-columns:1.2fr 1fr 1fr; padding:22px 28px; border-bottom:1px solid var(--line); }
    .metric { min-width:0; padding:0 22px; }
    .metric:first-child { padding-left:0; }
    .metric + .metric { border-left:1px solid var(--line); }
    .metric-label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
    .metric-value { margin-top:5px; font-size:26px; line-height:1.15; font-weight:600; }
    .metric-delta { min-height:18px; margin-top:4px; color:var(--muted); font-size:12px; }
    .primary { padding:24px 28px 28px; border-bottom:1px solid var(--line); }
    .eyebrow { margin-bottom:8px; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.07em; }
    .summary { max-width:70ch; font-size:16px; line-height:1.5; }
    .signals { display:grid; grid-template-columns:repeat(3,1fr); margin-top:24px; border-top:1px solid var(--line); }
    .signal { min-width:0; padding:18px 18px 0 0; color:var(--muted); }
    .signal + .signal { padding-left:18px; border-left:1px solid var(--line); }
    .number { display:block; margin-bottom:6px; color:var(--ink); font-size:12px; }
    .details { padding:0 28px; }
    details { border-bottom:1px solid var(--line); }
    summary { display:flex; justify-content:space-between; padding:17px 0; cursor:pointer; list-style:none; font-weight:500; }
    summary::-webkit-details-marker { display:none; }
    summary::after { content:"+"; color:var(--muted); font-size:20px; font-weight:300; line-height:16px; }
    details[open] summary::after { content:"−"; }
    .detail-body { padding:0 0 20px; color:var(--muted); }
    .detail-row { display:flex; justify-content:space-between; gap:18px; padding:9px 0; border-top:1px solid var(--soft); }
    .detail-row:first-child { border-top:0; }
    .detail-copy { max-width:70ch; }
    .action { width:100%; border:0; background:transparent; padding:18px 28px; text-align:left; cursor:pointer; }
    .action:hover,.action:focus-visible { background:var(--soft); outline:none; }
    .empty,.error { padding:36px 28px; color:var(--muted); }
    .loading { opacity:.55; pointer-events:none; }
    @media (max-width:560px) {
      .masthead,.controls,.report,.primary { padding-left:20px; padding-right:20px; }
      .metrics { padding:20px; }
      .metric { padding:0 12px; }
      .metric-value { font-size:21px; }
      .signals { grid-template-columns:1fr; }
      .signal,.signal + .signal { padding:14px 0; border-left:0; border-top:1px solid var(--line); }
      .details { padding:0 20px; }
      .selection { align-items:flex-start; flex-direction:column; }
      select { max-width:100%; text-align:left; }
    }
  </style>
</head>
<body>
  <main id="root" class="shell" aria-live="polite"><div class="empty">Loading Harbor…</div></main>
  <script>
    const root = document.getElementById("root");
    const pending = new Map();
    let requestId = 1;
    let dashboard = null;
    let activeTimeframe = null;
    let activePublication = "all";
    const periods = [["today","Today"],["last_7_days","7D"],["last_30_days","30D"],["quarter","QTR"],["ytd","YTD"],["custom","Custom"]];
    function el(tag,className,text){const n=document.createElement(tag);if(className)n.className=className;if(text!==undefined&&text!==null)n.textContent=String(text);return n;}
    function first(items,fallback){return Array.isArray(items)&&items.length?items[0]:fallback;}
    function list(items){return Array.isArray(items)?items.filter(Boolean):[];}
    function count(value){return value===null||value===undefined?"—":new Intl.NumberFormat(document.documentElement.lang||"en-US").format(value);}
    function percent(value){return value===null||value===undefined?"—":new Intl.NumberFormat(document.documentElement.lang||"en-US",{style:"percent",maximumFractionDigits:1}).format(value);}
    function reportDate(value,timeZone){if(!value)return"Not yet";const d=new Date(value);if(Number.isNaN(d.valueOf()))return String(value);try{return new Intl.DateTimeFormat(document.documentElement.lang||"en-US",{month:"short",day:"numeric",year:"numeric",timeZone:timeZone||"UTC"}).format(d);}catch(_){return d.toISOString().slice(0,10);}}
    function stateText(state){if(!state)return"";if(state.state==="not_supported")return state.detail||"Not supported";if(state.state==="insufficient_history")return state.detail||"Insufficient history";if(state.state==="no_data")return state.detail||"No data";return"";}
    function trend(intel,name){return list(intel?.trends).find(item=>item?.metric===name)||{};}
    function deltaText(item){if(item.delta===null||item.delta===undefined)return item.baseline===null||item.baseline===undefined?"Insufficient history":"";const sign=item.delta>0?"+":"";return`${sign}${(item.delta*100).toFixed(1)} pts vs ${String(item.baseline_label||"prior period").replaceAll("_"," ")}`;}
    function metric(label,value,delta,state){const n=el("div","metric");n.append(el("div","metric-label",label),el("div","metric-value",value),el("div","metric-delta",delta||stateText(state)));return n;}
    function row(left,right){const n=el("div","detail-row");n.append(el("div","detail-copy",left),el("div","detail-value",right));return n;}
    function section(title,items,renderItem){const d=document.createElement("details");d.append(el("summary",null,title));const body=el("div","detail-body");if(items.length){items.forEach((item,i)=>body.append(renderItem?renderItem(item,i):row(String(item),"")));}else{body.append(el("div",null,"No applicable data."));}d.append(body);return d;}
    function safePublications(latest){const values=list(latest?.metrics?.publications);if(values.length)return values;const m=latest?.metrics;return m?.publication_name?[{publication_id:"single",publication_name:m.publication_name,provider:null}]:[];}
    function render(data){
      dashboard=data;root.replaceChildren();
      const header=el("header","masthead");header.append(el("div","product","Harbor"));const ready=data.connection_status==="ready";const status=el("div","status");status.append(el("span","dot"),document.createTextNode(ready?"Connected":"Needs attention"));header.append(status);root.append(header);
      const latest=data.latest_intelligence;
      const controls=el("section","controls");const buttons=el("div","periods");const actual=activeTimeframe||latest?.metrics?.window?.label||latest?.intelligence?.window?.label||"last_30_days";
      periods.forEach(([value,label])=>{const b=el("button",`period${actual===value?" active":""}`,label);b.type="button";b.onclick=()=>selectPeriod(value);buttons.append(b);});controls.append(buttons);
      const selection=el("div","selection");selection.append(el("div","selection-label","Publication"));const select=document.createElement("select");const publications=safePublications(latest);const all=document.createElement("option");all.value="all";all.textContent=publications.length>1?"All publications":"Publication";select.append(all);publications.forEach(p=>{const o=document.createElement("option");o.value=String(p.publication_id||p.provider_id||"");o.textContent=p.publication_name||p.name||"Untitled publication";select.append(o);});select.value=activePublication;select.onchange=()=>selectPublication(select.value);selection.append(select);controls.append(selection);root.append(controls);
      if(!latest){root.append(el("div","empty","No matching intelligence report is saved yet. Ask ChatGPT to run Newsletter Intelligence for this selection."));addRunAction(actual);return;}
      const intel=latest.intelligence||{},metrics=latest.metrics||{},post=metrics.latest_post||{};
      const report=el("section","report");const heading=el("div","report-heading");heading.append(el("span",null,"Intelligence —"),el("span","report-date",reportDate(latest.finished_at,data.workspace?.timezone)));report.append(heading);root.append(report);
      const openTrend=trend(intel,"Open rate"),clickTrend=trend(intel,"Click rate");const metricsRow=el("section","metrics");metricsRow.append(metric("Audience",count(metrics.active_subscribers),"",metrics.metric_states?.subscribers),metric("Open",percent(post.open_rate??metrics.avg_open_rate),deltaText(openTrend),post.metric_states?.open_rate),metric("Click",percent(post.click_rate??metrics.avg_click_rate),deltaText(clickTrend),post.metric_states?.click_rate));root.append(metricsRow);
      const primary=el("section","primary");primary.append(el("div","eyebrow","What changed"),el("div","summary",first(intel.what_changed,"Harbor needs another comparable result before measuring change.")));const signalItems=[...list(intel.anomalies),...list(intel.audience_signals),...list(intel.why_it_matters)].slice(0,3);const signals=el("div","signals");signalItems.forEach((item,i)=>{const n=el("div","signal");n.append(el("span","number",String(i+1).padStart(2,"0")),el("div",null,item));signals.append(n);});primary.append(signals);root.append(primary);
      const details=el("div","details");const top=[intel.strongest_open&&["Strongest opens",intel.strongest_open],intel.strongest_click&&["Strongest clicks",intel.strongest_click]].filter(Boolean);details.append(section("Top content",top,item=>row(`${item[0]} · ${item[1].title||"Untitled"}${item[1].publication_name?` · ${item[1].publication_name}`:""}`,item[0].includes("opens")?percent(item[1].open_rate):percent(item[1].click_rate))));details.append(section("Opportunities",list(intel.recommendations)));const watch=[...list(intel.anomalies),...list(intel.why_it_matters).filter(x=>/cannot|need|insufficient|unavailable/i.test(x))];details.append(section("Watch",[...new Set(watch)]));details.append(section("Publications",publications,p=>row(`${p.publication_name||p.name||"Untitled"} · ${p.provider||"Newsletter"}`,`${count(p.active_subscribers)} subscribers`)));details.append(section("Sources",list(data.sources),s=>row(s.label||s.provider||"Source",s.status||"unknown")));details.append(section("Recent runs",list(data.recent_runs).slice(0,5),r=>row(`${r.worker_id} · ${reportDate(r.finished_at||r.started_at,data.workspace?.timezone)}`,r.status)));details.append(section("Workers",list(data.workers),w=>row(w.label||w.id,w.enabled?(w.runnable?"Enabled":"Unavailable"):"Disabled")));root.append(details);addRunAction(actual);
    }
    function addRunAction(timeframe){const b=el("button","action","Run Newsletter Intelligence →");b.type="button";b.onclick=()=>followUp(`Run Newsletter Intelligence for ${timeframe.replaceAll("_"," ")}${activePublication!=="all"?` for publication ${activePublication}`:" across all publications"}.`);root.append(b);}
    async function selectPeriod(value){if(value==="custom"){followUp("Ask me for a custom newsletter intelligence date range, then run Harbor with those exact dates.");return;}activeTimeframe=value;await loadSaved();}
    async function selectPublication(value){activePublication=value;await loadSaved();}
    async function loadSaved(){root.classList.add("loading");try{const args={timeframe:activeTimeframe||"last_30_days"};if(activePublication!=="all"){args.view="publication";args.publication_ids=[activePublication];}else{args.view="portfolio";}const result=await request("tools/call",{name:"harbor_newsletter_intelligence",arguments:args});const next=result?.structuredContent;render({...dashboard,latest_intelligence:next?.found?next.latest_intelligence:null});}catch(_){root.classList.remove("loading");}}
    function followUp(prompt){if(window.openai?.sendFollowUpMessage){window.openai.sendFollowUpMessage({prompt});}else{request("ui/message",{role:"user",content:[{type:"text",text:prompt}]}).catch(()=>{});}}
    function request(method,params){const id=requestId++;window.parent.postMessage({jsonrpc:"2.0",id,method,params},"*");return new Promise((resolve,reject)=>pending.set(id,{resolve,reject}));}
    function notify(method,params){window.parent.postMessage({jsonrpc:"2.0",method,params},"*");}
    async function connect(){try{await request("ui/initialize",{appInfo:{name:"Harbor",version:"1.0.0-rc.6"},appCapabilities:{},protocolVersion:"2026-01-26"});notify("ui/notifications/initialized",{});if(window.openai?.toolOutput)render(window.openai.toolOutput);}catch(_){if(window.openai?.toolOutput){render(window.openai.toolOutput);return;}root.replaceChildren(el("div","error","Harbor could not load. Refresh the connection and try again."));}}
    window.addEventListener("message",event=>{if(event.source!==window.parent)return;const message=event.data;if(!message||message.jsonrpc!=="2.0")return;if(message.id!==undefined&&pending.has(message.id)){const handler=pending.get(message.id);pending.delete(message.id);message.error?handler.reject(message.error):handler.resolve(message.result);return;}if(message.method==="ui/notifications/tool-result"&&message.params?.structuredContent)render(message.params.structuredContent);},{passive:true});
    connect();
  </script>
</body>
</html>"""
