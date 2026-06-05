# ruff: noqa: E501, SIM105
# E501: dashboard HTML/CSS/JS is intentionally compact.
# SIM105: try/except in the JS string is not Python code.
"""FastAPI dashboard application for 7-bridges usage metrics."""

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from .reader import (
    compute_activity,
    compute_cache_efficiency,
    compute_model_distribution,
    compute_stats,
    compute_tool_stats,
)

app = FastAPI(title="7 Bridges Dashboard", version="0.2.0")


@app.get("/favicon.svg")
def favicon() -> Response:
    """Serve the 7B favicon."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#161b22"/>
  <text x="16" y="23" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" font-size="18" font-weight="700" fill="#d4a5ff">7B</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats")
def api_stats(
    hours: int = Query(default=24, ge=1, le=720),
    backend: str | None = Query(default=None),
) -> JSONResponse:
    """Return aggregated dashboard statistics as JSON."""
    backends = [b.strip() for b in backend.split(",") if b.strip()] if backend else None
    stats = compute_stats(hours=hours, backends=backends)
    return JSONResponse(content=stats)


@app.get("/api/tools")
def api_tools(
    hours: int = Query(default=24, ge=1, le=720),
    backend: str | None = Query(default=None),
) -> JSONResponse:
    """Return tool usage analytics as JSON."""
    backends = [b.strip() for b in backend.split(",") if b.strip()] if backend else None
    stats = compute_tool_stats(hours=hours, backends=backends)
    return JSONResponse(content=stats)


@app.get("/api/activity")
def api_activity(
    hours: int = Query(default=24, ge=1, le=720),
    backend: str | None = Query(default=None),
) -> JSONResponse:
    """Return activity pattern analytics as JSON."""
    backends = [b.strip() for b in backend.split(",") if b.strip()] if backend else None
    stats = compute_activity(hours=hours, backends=backends)
    return JSONResponse(content=stats)


@app.get("/api/models")
def api_models(
    hours: int = Query(default=24, ge=1, le=720),
    backend: str | None = Query(default=None),
) -> JSONResponse:
    """Return per-model token/cache breakdown as JSON."""
    backends = [b.strip() for b in backend.split(",") if b.strip()] if backend else None
    stats = compute_model_distribution(hours=hours, backends=backends)
    return JSONResponse(content=stats)


@app.get("/api/cache")
def api_cache(
    hours: int = Query(default=24, ge=1, le=720),
    backend: str | None = Query(default=None),
) -> JSONResponse:
    """Return cache efficiency analytics as JSON."""
    backends = [b.strip() for b in backend.split(",") if b.strip()] if backend else None
    stats = compute_cache_efficiency(hours=hours, backends=backends)
    return JSONResponse(content=stats)


@app.get("/static/chart.umd.min.js")
def chart_js() -> FileResponse:
    """Serve Chart.js locally for offline use (no CDN dependency)."""
    static_dir = Path(__file__).parent / "static"
    return FileResponse(
        static_dir / "chart.umd.min.js",
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """Serve the single-page usage dashboard."""
    return _DASHBOARD_HTML


_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>7 Bridges Dashboard</title>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<script src="/static/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;background:#0d1117;color:#c9d1d9;line-height:1.5;min-height:100vh}
a{color:#d4a5ff;text-decoration:none}a:hover{text-decoration:underline}

/* Header */
header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;position:sticky;top:0;z-index:10}
.header-left{display:flex;align-items:center;gap:10px}
.header-left h1{font-size:1.15rem;font-weight:600;color:#f0f6fc}
.header-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pill{background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:20px;padding:3px 12px;font-size:0.78rem;cursor:pointer;transition:all 0.15s;white-space:nowrap;font-family:inherit}
.pill:hover{background:#30363d;border-color:#d4a5ff}
.pill.active{background:#d4a5ff20;border-color:#d4a5ff;color:#d4a5ff}
select{background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:3px 8px;border-radius:4px;font-size:0.75rem;font-family:inherit}
select:focus{outline:2px solid #d4a5ff;outline-offset:1px}
.status{display:flex;align-items:center;gap:6px;font-size:0.75rem;color:#8b949e}
.dot{width:7px;height:7px;border-radius:50%;background:#3fb950}
.dot.fetching{animation:pulse 0.8s ease-in-out infinite}
.dot.error{background:#f85149}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}

/* Layout */
main{padding:20px;max-width:1440px;margin:0 auto}

/* Stat cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:20px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px;transition:border-color 0.15s}
.card:hover{border-color:#d4a5ff40}
.card-label{font-size:0.7rem;text-transform:uppercase;letter-spacing:0.04em;color:#8b949e;margin-bottom:2px}
.card-value{font-size:1.6rem;font-weight:700;color:#f0f6fc;line-height:1.15;font-variant-numeric:tabular-nums}
.card-trend{font-size:0.75rem;margin-top:2px;font-weight:500}
.card-trend.up{color:#3fb950}
.card-trend.down{color:#f85149}
.card-trend.neutral{color:#8b949e}
.card.accent .card-value{color:#d4a5ff}
.card.success .card-value{color:#3fb950}
.card.warning .card-value{color:#d29922}
.card.danger .card-value{color:#f85149}

/* Charts */
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px;margin-bottom:20px}
.chart-panel{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px 18px}
.chart-panel.full{grid-column:1/-1}
.chart-panel h2{font-size:0.85rem;font-weight:600;color:#c9d1d9;margin-bottom:8px}
.chart-wrap{position:relative;width:100%;height:240px}
.chart-wrap canvas{width:100%!important;height:100%!important}
.chart-wrap.donut{width:300px;height:300px;margin:0 auto}

/* Tables */
.table-section{margin-bottom:20px}
.table-section h2{font-size:0.9rem;font-weight:600;color:#f0f6fc;margin-bottom:10px}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:0.78rem}
thead th{background:#161b22;border-bottom:2px solid #30363d;padding:8px 10px;text-align:left;color:#c9d1d9;font-weight:600;white-space:nowrap;cursor:pointer;user-select:none;position:sticky;top:0}
thead th:hover{color:#f0f6fc}
thead th .sort-arrow{font-size:0.65rem;margin-left:3px;opacity:0.5}
thead th.sorted .sort-arrow{opacity:1;color:#d4a5ff}
tbody td{padding:6px 10px;border-bottom:1px solid #21262d;white-space:nowrap}
tbody tr:hover{background:#1c2128}
tbody td.num{text-align:right;font-variant-numeric:tabular-nums}
.chip{display:inline-block;background:#d4a5ff20;color:#d4a5ff;border-radius:4px;padding:1px 7px;font-size:0.7rem;font-weight:500}

/* Tabs for table section */
.tabs{display:flex;gap:2px;margin-bottom:12px;flex-wrap:wrap}
.tab-btn{background:transparent;border:1px solid #30363d;color:#8b949e;padding:5px 14px;border-radius:6px 6px 0 0;font-size:0.78rem;cursor:pointer;font-family:inherit;border-bottom:none}
.tab-btn:hover{color:#c9d1d9;background:#1c2128}
.tab-btn.active{background:#161b22;color:#d4a5ff;border-color:#30363d;font-weight:600}

/* Cost disclaimer */
.cost-note{font-size:0.68rem;color:#484f58;margin:-6px 0 16px 0;padding:0 4px}

/* Footer */
footer{text-align:center;padding:14px;color:#484f58;font-size:0.72rem;border-top:1px solid #21262d}

.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}

@media(max-width:768px){
  header{padding:10px 14px}
  main{padding:14px}
  .cards{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
  .charts{grid-template-columns:1fr}
  .card-value{font-size:1.3rem}
  .chart-wrap{height:200px}
}
</style>
</head>
<body>
<header>
  <div class="header-left">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#d4a5ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 9V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-3"/><path d="M2 12h8l2 2 4-4"/></svg>
    <h1>7 Bridges Dashboard</h1>
  </div>
  <div class="header-right">
    <div class="filter-pills" id="filter-pills"></div>
    <label for="window-select" style="font-size:0.7rem;color:#8b949e;text-transform:uppercase">Window</label>
    <select id="window-select">
      <option value="0.5">30m</option><option value="1">1h</option>
      <option value="2">2h</option><option value="6">6h</option>
      <option value="8">8h</option><option value="24" selected>24h</option>
      <option value="168">7d</option><option value="720">30d</option>
    </select>
    <label for="refresh-select" style="font-size:0.7rem;color:#8b949e;text-transform:uppercase">Refresh</label>
    <select id="refresh-select">
      <option value="0">Off</option><option value="15000">15s</option>
      <option value="30000">30s</option><option value="60000" selected>60s</option>
      <option value="300000">5m</option>
    </select>
    <div class="status">
      <span class="dot ok" id="status-dot"></span>
      <span id="last-updated">--</span>
    </div>
  </div>
</header>
<main>
  <div class="cards" id="cards"></div>
  <div class="cost-note">Cost estimates based on default Anthropic pricing ($0.40/M input, $4.00/M output). Actual costs vary by backend and model. For directional use only.</div>
  <div class="charts">
    <div class="chart-panel"><h2>Requests / Hour</h2><div class="chart-wrap"><canvas id="chart-reqs"></canvas></div></div>
    <div class="chart-panel"><h2>Tokens / Hour</h2><div class="chart-wrap"><canvas id="chart-tokens"></canvas></div></div>
    <div class="chart-panel"><h2>Cost / Hour</h2><div class="chart-wrap"><canvas id="chart-cost"></canvas></div></div>
    <div class="chart-panel"><h2>Model Distribution</h2><div class="chart-wrap donut"><canvas id="chart-model-donut"></canvas></div></div>
    <div class="chart-panel"><h2>Hourly Activity</h2><div class="chart-wrap"><canvas id="chart-hourly"></canvas></div></div>
    <div class="chart-panel"><h2>Feature Adoption</h2><p style="font-size:0.7rem;color:#8b949e;margin-bottom:6px">% of requests using each feature</p><div class="chart-wrap donut"><canvas id="chart-features"></canvas></div></div>
    <div class="chart-panel full"><h2>Errors / Hour</h2><div class="chart-wrap" style="height:180px"><canvas id="chart-errors"></canvas></div></div>
  </div>
  <div class="tabs">
    <button class="tab-btn active" data-tab="backend">Backends</button>
    <button class="tab-btn" data-tab="model">Models</button>
    <button class="tab-btn" data-tab="session">Sessions</button>
    <button class="tab-btn" data-tab="errors">Errors</button>
    <button class="tab-btn" data-tab="requests">Recent Requests</button>
  </div>
  <div id="tab-backend" class="table-section"><div class="table-wrap"><table id="table-backend"><thead></thead><tbody></tbody></table></div></div>
  <div id="tab-model" class="table-section" style="display:none"><div class="table-wrap"><table id="table-model"><thead></thead><tbody></tbody></table></div></div>
  <div id="tab-session" class="table-section" style="display:none"><div class="table-wrap"><table id="table-session"><thead></thead><tbody></tbody></table></div></div>
  <div id="tab-errors" class="table-section" style="display:none"><div class="table-wrap"><table id="table-errors"><thead></thead><tbody></tbody></table></div></div>
  <div id="tab-requests" class="table-section" style="display:none"><div class="table-wrap"><table id="table-requests"><thead></thead><tbody></tbody></table></div></div>
</main>
<footer>7 Bridges Dashboard &mdash; observability for multi-harness agentic development</footer>

<script>
(function(){
"use strict";

/* ---- Chart.js theme ---- */
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#30363d';
Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif';
Chart.defaults.font.size = 11;
Chart.defaults.plugins.tooltip.backgroundColor = '#161b22';
Chart.defaults.plugins.tooltip.borderColor = '#30363d';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.titleFont = {weight:'600'};
Chart.defaults.plugins.legend.labels.usePointStyle = false;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 8;

var COLORS = {
  purple: '#d4a5ff',
  blue: '#58a6ff',
  green: '#3fb950',
  orange: '#d29922',
  red: '#f85149',
  teal: '#39d353',
  pink: '#f778ba',
  gray: '#484f58',
  grid: '#21262d',
  axis: '#30363d'
};

var MODEL_COLORS = ['#d4a5ff','#58a6ff','#3fb950','#d29922','#f778ba','#39d353','#f85149','#a5d6ff','#ffa198','#f0c000'];
var chartInstances = {};

function shortModel(name){
  return name.replace(/^claude-/,'').replace(/-20251001$/,'').replace(/-latest$/,'');
}

function destroyCharts(){
  Object.keys(chartInstances).forEach(function(k){
    if(chartInstances[k]){ chartInstances[k].destroy(); chartInstances[k] = null; }
  });
}

/* ---- Utilities ---- */
function esc(s){var d=document.createElement('div');d.textContent=s==null?'':String(s);return d.innerHTML;}
function fmtNum(n){
  if(n==null)return'0';
  if(n>=1e9)return(n/1e9).toFixed(1)+'B';
  if(n>=1e6)return(n/1e6).toFixed(1)+'M';
  if(n>=1e3)return(n/1e3).toFixed(1)+'K';
  return String(Math.floor(n));
}
function fmtCost(n){
  if(n==null)return'$0.00';
  var v=Number(n);
  if(v<0.01)return'<$0.01';
  if(v<1)return'$'+v.toFixed(2);
  if(v<1000)return'$'+v.toFixed(1);
  return'$'+(v/1e3).toFixed(1)+'K';
}
function fmtPct(n){if(n==null)return'0%';return Number(n).toFixed(1)+'%';}
function fmtMs(n){
  if(n==null)return'--';
  var v=Number(n);
  if(v<1000)return v.toFixed(0)+'ms';
  return(v/1000).toFixed(1)+'s';
}
function fmtTime(ts){
  if(!ts)return'--';
  try{return new Date(ts).toLocaleString();}catch(e){return ts;}
}
function fmtHourLabel(label){
  try{var d=new Date(label);if(isNaN(d.getTime()))return label;
    return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}catch(e){return label;}
}
function fmtTrend(pct){
  if(pct==null)return'<span class="card-trend neutral">&mdash;</span>';
  var abs=Math.abs(pct);
  var arrow=pct>0?'&#9650;':'&#9660;';
  var cls=pct>0?'up':'down';
  return'<span class="card-trend '+cls+'">'+arrow+' '+abs.toFixed(1)+'%</span>';
}

/* ---- State ---- */
var activeBackends=[],allBackends=[],windowHours=parseInt(document.getElementById('window-select').value,10)||24,refreshMs=60000,refreshTimer=null;
var statsData=null,toolsData=null,activityData=null;
var lastSort={table:null,col:null,asc:true};

/* ---- Chart factory functions ---- */

function commonBarOpts(yMax, yLabel){
  return {
    responsive:true,maintainAspectRatio:false,
    scales:{
      x:{grid:{color:COLORS.grid},ticks:{maxTicksLimit:12,color:'#8b949e',font:{size:9},
        callback:function(v,i){var labels=this.chart.data.labels;return labels.length<=12||i%Math.ceil(labels.length/8)===0?fmtHourLabel(labels[i]):'';}}},
      y:{grid:{color:COLORS.grid},max:yMax,ticks:{color:'#8b949e',font:{size:9},
        callback:function(v){return v>=1e6?(v/1e6).toFixed(1)+'M':v>=1e3?(v/1e3).toFixed(1)+'K':v;}},
        title:{display:!!yLabel,text:yLabel||'',color:'#8b949e'}}
    },
    plugins:{legend:{display:false},tooltip:{callbacks:{title:function(ctx){return fmtHourLabel(ctx[0].label);}}}}
  };
}

function createBarChart(canvasId,labels,values,color,yLabel){
  var ctx=document.getElementById(canvasId);if(!ctx)return;
  var hasData=values.some(function(v){return v>0;});
  if(!hasData)return;
  var maxVal=Math.max.apply(null,values)||10;
  if(maxVal<10)maxVal=10;
  var niceMax=maxVal*1.2;
  chartInstances[canvasId]=new Chart(ctx,{
    type:'bar',
    data:{labels:labels,datasets:[{data:values,backgroundColor:color,borderRadius:2,borderSkipped:false}]},
    options:commonBarOpts(niceMax,yLabel)
  });
}

function createStackedBarChart(canvasId,labels,hitVals,missVals,outVals,inVals){
  var ctx=document.getElementById(canvasId);if(!ctx)return;
  var hasData=false,computedMiss=[];
  for(var i=0;i<labels.length;i++){
    var hasCache=hitVals[i]>0||missVals[i]>0;
    computedMiss[i]=hasCache?missVals[i]:(inVals&&inVals[i]>0?inVals[i]:0);
    if(hitVals[i]>0||computedMiss[i]>0||outVals[i]>0)hasData=true;
  }
  if(!hasData)return;
  var maxVal=0;
  for(var i=0;i<labels.length;i++){maxVal=Math.max(maxVal,hitVals[i]+computedMiss[i]+outVals[i]);}
  if(maxVal<10)maxVal=10;
  chartInstances[canvasId]=new Chart(ctx,{
    type:'bar',
    data:{labels:labels,datasets:[
      {label:'Cache hit',data:hitVals,backgroundColor:COLORS.blue,borderRadius:0,borderSkipped:false,stack:'tokens'},
      {label:'Cache miss',data:computedMiss,backgroundColor:COLORS.green,borderRadius:0,borderSkipped:false,stack:'tokens'},
      {label:'Output',data:outVals,backgroundColor:COLORS.orange,borderRadius:{topLeft:2,topRight:2},borderSkipped:false,stack:'tokens'}
    ]},
    options:Object.assign({},commonBarOpts(maxVal*1.2),{
      plugins:{legend:{display:true,position:'top',labels:{boxWidth:10,boxHeight:10,padding:12,font:{size:10},color:'#8b949e',usePointStyle:false}},
        tooltip:{callbacks:{title:function(ctx){return fmtHourLabel(ctx[0].label);},
          label:function(ctx){return ctx.dataset.label+': '+fmtNum(ctx.raw)+' tokens';}}}
      }
    })
  });
}

function createDoughnutChart(canvasId,labels,values,colors,title){
  var ctx=document.getElementById(canvasId);if(!ctx)return;
  var hasData=values.some(function(v){return v>0;});
  if(!hasData)return;
  chartInstances[canvasId]=new Chart(ctx,{
    type:'doughnut',
    data:{labels:labels,datasets:[{data:values,backgroundColor:colors,borderColor:'#161b22',borderWidth:2}]},
    options:{
      responsive:true,maintainAspectRatio:true,aspectRatio:1,
      plugins:{legend:{position:'bottom',align:'center',labels:{padding:8,boxWidth:10,boxHeight:10,font:{size:10},color:'#8b949e',usePointStyle:false}},
        tooltip:{callbacks:{label:function(ctx){return ctx.label+': '+fmtNum(ctx.raw)+' tokens';}}}}
    }
  });
}

function createHorizontalBarChart(canvasId,labels,values,colors){
  var ctx=document.getElementById(canvasId);if(!ctx)return;
  var hasData=values.some(function(v){return v>0;});
  if(!hasData)return;
  chartInstances[canvasId]=new Chart(ctx,{
    type:'bar',
    data:{labels:labels,datasets:[{data:values,backgroundColor:colors,borderRadius:2,borderSkipped:false}]},
    options:{
      indexAxis:'y',
      responsive:true,maintainAspectRatio:false,
      scales:{
        x:{grid:{color:COLORS.grid},ticks:{color:'#8b949e',font:{size:9},
          callback:function(v){return v>=1e3?(v/1e3).toFixed(1)+'K':v;}}},
        y:{grid:{display:false},ticks:{color:'#c9d1d9',font:{size:10},autoSkip:false}}
      },
      plugins:{legend:{display:false}}
    }
  });
}

/* ---- Table rendering ---- */

var COL_DEFS={
  backend:[
    {key:'backend',title:'Backend'},{key:'requests',title:'Requests',num:true,fmt:fmtNum},
    {key:'input_tokens',title:'Input Tokens',num:true,fmt:fmtNum},{key:'output_tokens',title:'Output Tokens',num:true,fmt:fmtNum},
    {key:'cost',title:'Cost',num:true,fmt:fmtCost},{key:'avg_latency_ms',title:'Avg Latency',num:true,fmt:fmtMs},
    {key:'errors',title:'Errors',num:true},{key:'error_rate',title:'Error Rate',num:true,fmt:fmtPct},
    {key:'cache_hit_rate',title:'Cache Hit Rate',num:true,fmt:fmtPct}
  ],
  model:[
    {key:'model_alias',title:'Model'},{key:'backend',title:'Backend'},{key:'requests',title:'Requests',num:true,fmt:fmtNum},
    {key:'input_tokens',title:'Input Tokens',num:true,fmt:fmtNum},{key:'output_tokens',title:'Output Tokens',num:true,fmt:fmtNum},
    {key:'cost',title:'Cost',num:true,fmt:fmtCost},{key:'avg_latency_ms',title:'Avg Latency',num:true,fmt:fmtMs}
  ],
  session:[
    {key:'session_id',title:'Session'},{key:'requests',title:'Requests',num:true,fmt:fmtNum},
    {key:'input_tokens',title:'Input Tokens',num:true,fmt:fmtNum},{key:'output_tokens',title:'Output Tokens',num:true,fmt:fmtNum},
    {key:'cost',title:'Cost',num:true,fmt:fmtCost},{key:'last_active',title:'Last Active',fmt:fmtTime}
  ],
  errors:[
    {key:'timestamp',title:'Time',fmt:fmtTime},{key:'bridge',title:'Backend'},{key:'model_alias',title:'Model'},
    {key:'status_code',title:'Status',num:true},{key:'error_type',title:'Error Type'},{key:'error_message',title:'Message'}
  ],
  requests:[
    {key:'timestamp',title:'Time',fmt:fmtTime},{key:'model_alias',title:'Model'},{key:'bridge',title:'Backend'},
    {key:'stream',title:'Stream'},{key:'estimated_cost_usd',title:'Cost',fmt:fmtCost},
    {key:'latency_ms',title:'Latency',fmt:fmtMs},{key:'session_id',title:'Session'}
  ]
};

function renderTable(tableId,columns,rows,defId){
  var table=document.getElementById(tableId),thead=table.querySelector('thead'),tbody=table.querySelector('tbody');
  var hhtml='<tr>';
  for(var i=0;i<columns.length;i++){
    var col=columns[i],arrow='';
    if(lastSort.table===defId&&lastSort.col===col.key){
      arrow=' <span class="sort-arrow">'+(lastSort.asc?'&#9650;':'&#9660;')+'</span>';
    }else{arrow=' <span class="sort-arrow">&#9650;&#9660;</span>';}
    hhtml+='<th class="'+(lastSort.table===defId&&lastSort.col===col.key?' sorted':'')+'" data-col="'+esc(col.key)+'">'+esc(col.title)+arrow+'</th>';
  }
  hhtml+='</tr>';thead.innerHTML=hhtml;
  var bhtml='';
  for(var r=0;r<rows.length;r++){
    bhtml+='<tr>';
    for(var c=0;c<columns.length;c++){
      var col2=columns[c],val=rows[r][col2.key],display=col2.fmt?col2.fmt(val):(val!=null?esc(String(val)):'--');
      if(col2.key==='stream')display=val?'<span class="chip">stream</span>':'<span class="chip" style="background:#30363d;color:#8b949e">batch</span>';
      bhtml+='<td class="'+(col2.num?'num':'')+'">'+display+'</td>';
    }
    bhtml+='</tr>';
  }
  tbody.innerHTML=bhtml;
  thead.querySelectorAll('th').forEach(function(th){th.addEventListener('click',function(){
    var colKey=th.getAttribute('data-col');sortTable(defId,colKey,columns,rows,tableId,thead);});});
}
function sortTable(defId,colKey,columns,rows,tableId,thead){
  if(lastSort.table===defId&&lastSort.col===colKey){lastSort.asc=!lastSort.asc;}
  else{lastSort.table=defId;lastSort.col=colKey;lastSort.asc=true;}
  var colDef=null;
  for(var i=0;i<columns.length;i++){if(columns[i].key===colKey){colDef=columns[i];break;}}
  var isNum=colDef&&colDef.num;
  rows.sort(function(a,b){
    var va=a[colKey],vb=b[colKey];
    if(va==null&&vb==null)return 0;if(va==null)return 1;if(vb==null)return-1;
    if(isNum){va=Number(va);vb=Number(vb);}else{va=String(va).toLowerCase();vb=String(vb).toLowerCase();}
    if(va<vb)return lastSort.asc?-1:1;if(va>vb)return lastSort.asc?1:-1;return 0;
  });
  renderTable(tableId,columns,rows,defId);
}

/* ---- Filter pills ---- */

function buildFilterPills(){
  var container=document.getElementById('filter-pills'),html='<button class="pill active" data-backend="all">All</button>';
  for(var i=0;i<allBackends.length;i++){
    var b=allBackends[i];html+='<button class="pill" data-backend="'+esc(b)+'">'+esc(b.charAt(0).toUpperCase()+b.slice(1))+'</button>';
  }
  container.innerHTML=html;
  container.querySelectorAll('.pill').forEach(function(btn){btn.addEventListener('click',function(){
    var bk=btn.getAttribute('data-backend');
    if(bk==='all'){activeBackends=[];container.querySelectorAll('.pill').forEach(function(p){p.classList.remove('active');});btn.classList.add('active');}
    else{
      var allBtn=container.querySelector('[data-backend="all"]');if(allBtn)allBtn.classList.remove('active');
      var idx=activeBackends.indexOf(bk);
      if(idx>=0){activeBackends.splice(idx,1);btn.classList.remove('active');}else{activeBackends.push(bk);btn.classList.add('active');}
      if(activeBackends.length===0){activeBackends=[];if(allBtn)allBtn.classList.add('active');}
    }
    fetchAll();
  });});
}

/* ---- Tab switching ---- */
document.querySelector('.tabs').addEventListener('click',function(e){
  var btn=e.target.closest('.tab-btn');if(!btn)return;
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  var tab=btn.getAttribute('data-tab');
  ['backend','model','session','errors','requests'].forEach(function(t){
    document.getElementById('tab-'+t).style.display=t===tab?'':'none';
  });
});

/* ---- Status ---- */
function setStatus(state){
  var dot=document.getElementById('status-dot');dot.className='dot '+state;
  document.getElementById('last-updated').textContent='Updated: '+new Date().toLocaleTimeString();
}

/* ---- Main render ---- */

function refreshUI(){
  destroyCharts();
  if(!statsData)return;
  var s=statsData,ts=s.time_series,labels=ts.labels;

  // ---- Stat cards ----
  var totalTokens=s.aggregates.total_input_tokens+s.aggregates.total_output_tokens;
  var costPerReq=s.aggregates.total_requests>0?'$'+(s.aggregates.total_cost/s.aggregates.total_requests).toFixed(4):'$0.00';
  var trends=s.trends||{};
  var cards=[
    {cls:'',label:'Requests ('+windowHours+'h)',value:fmtNum(s.aggregates.total_requests),trend:fmtTrend(trends.requests_pct)},
    {cls:'',label:'Tokens',value:fmtNum(totalTokens),trend:fmtTrend(trends.tokens_pct)},
    {cls:'accent',label:'Est. Cost',value:fmtCost(s.aggregates.total_cost),sub:'avg '+costPerReq+'/req',trend:fmtTrend(trends.cost_pct)},
    {cls:'success',label:'Cache Hit Rate',value:fmtPct(s.aggregates.cache_hit_rate),trend:''},
    {cls:s.aggregates.error_rate>5?'danger':'warning',label:'Error Rate',value:fmtPct(s.aggregates.error_rate),sub:s.total_errors_24h+' errors',trend:fmtTrend(trends.errors_pct)},
    {cls:'',label:'Avg Latency',value:fmtMs(s.aggregates.avg_latency_ms),trend:''}
  ];
  var cardsHtml='';
  for(var i=0;i<cards.length;i++){
    var c=cards[i];
    cardsHtml+='<div class="card '+c.cls+'"><div class="card-label">'+esc(c.label)+'</div><div class="card-value">'+esc(c.value)+'</div>'+c.trend+(c.sub?'<div class="card-sub" style="font-size:0.72rem;color:#8b949e;margin-top:1px">'+esc(c.sub)+'</div>':'')+'</div>';
  }
  document.getElementById('cards').innerHTML=cardsHtml;

  // ---- Charts ----
  // Requests bar
  createBarChart('chart-reqs',labels,ts.requests,COLORS.purple,'Requests');

  // Tokens stacked bar
  createStackedBarChart('chart-tokens',labels,ts.tokens_cache_hit||[],ts.tokens_cache_miss||[],ts.tokens_out||[],ts.tokens_in||[]);

  // Cost bar
  createBarChart('chart-cost',labels,ts.cost,COLORS.orange,'Cost (USD)');

  // Model donut — group small segments (<2%) into "Other"
  if(s.by_model&&s.by_model.length>0){
    var mNames=[],mVals=[],mColors=[];
    var totalTok=0;
    for(var i=0;i<s.by_model.length;i++){totalTok+=s.by_model[i].input_tokens+s.by_model[i].output_tokens;}
    var otherTok=0;
    for(var i=0;i<s.by_model.length;i++){
      var tok=s.by_model[i].input_tokens+s.by_model[i].output_tokens;
      var pct=tok/totalTok*100;
      if(pct>=2||s.by_model.length<=3){
        mNames.push(shortModel(s.by_model[i].model_alias));mVals.push(tok);
        mColors.push(MODEL_COLORS[mNames.length-1]);
      }else{otherTok+=tok;}
    }
    if(otherTok>0){mNames.push('Other');mVals.push(otherTok);mColors.push(COLORS.gray);}
    createDoughnutChart('chart-model-donut',mNames,mVals,mColors);
  }

  // Hourly activity chart
  if(activityData&&activityData.hourly){
    var hLabels=[],hVals=[];
    for(var i=0;i<24;i++){hLabels.push(String(i));hVals.push(activityData.hourly[i]||0);}
    var maxH=Math.max.apply(null,hVals)||10;
    var hourlyColors=[];
    for(var i=0;i<24;i++){hourlyColors.push(i===activityData.peak_hour?COLORS.purple:COLORS.blue+'80');}
    var ctxH=document.getElementById('chart-hourly');
    if(ctxH&&hVals.some(function(v){return v>0;})){
      chartInstances['chart-hourly']=new Chart(ctxH,{
        type:'bar',
        data:{labels:hLabels,datasets:[{data:hVals,backgroundColor:hourlyColors,borderRadius:2,borderSkipped:false}]},
        options:Object.assign({},commonBarOpts(maxH*1.2,'Requests'),{
          scales:Object.assign({},commonBarOpts(maxH*1.2,'Requests').scales,{
            x:{grid:{color:COLORS.grid},ticks:{color:'#8b949e',font:{size:9}},title:{display:true,text:'Hour of day (UTC)',color:'#8b949e'}}
          })
        })
      });
    }
  }

  // Feature adoption donut (replaces broken tool ranking — tool_names are declarations, not calls)
  if(toolsData&&toolsData.feature_adoption){
    var fa=toolsData.feature_adoption;
    var fLabels=['Tools','MCP','Thinking'],fVals=[fa.tools.pct,fa.mcp.pct,fa.thinking.pct];
    var fColors=[COLORS.purple,COLORS.blue,COLORS.green];
    // Add streaming % from stats aggregates
    if(s.aggregates.stream_pct!==undefined){
      fLabels.push('Streaming');fVals.push(s.aggregates.stream_pct);fColors.push(COLORS.orange);
    }
    createDoughnutChart('chart-features',fLabels,fVals,fColors);
  }

  // Errors bar
  var errVals=ts.errors||[],errLabels=labels;
  createBarChart('chart-errors',errLabels,errVals,COLORS.red,'Errors');

  // ---- Tables ----
  renderTable('table-backend',COL_DEFS.backend,s.by_backend||[],'backend');
  renderTable('table-model',COL_DEFS.model,s.by_model||[],'model');
  renderTable('table-session',COL_DEFS.session,s.by_session||[],'session');
  renderTable('table-errors',COL_DEFS.errors,s.recent_errors||[],'errors');
  renderTable('table-requests',COL_DEFS.requests,s.recent_requests||[],'requests');

  // Build filter pills from backends
  if(allBackends.length===0&&s.by_backend&&s.by_backend.length>0){
    for(var i=0;i<s.by_backend.length;i++){allBackends.push(s.by_backend[i].backend);}
    buildFilterPills();
  }
}

/* ---- Data fetching ---- */

function buildUrl(path){
  var url=path+'?hours='+windowHours;
  if(activeBackends.length>0)url+='&backend='+encodeURIComponent(activeBackends.join(','));
  return url;
}

function fetchAll(){
  setStatus('fetching');
  var p1=fetch(buildUrl('/api/stats')).then(function(r){return r.json();});
  var p2=fetch(buildUrl('/api/tools')).then(function(r){return r.json();});
  var p3=fetch(buildUrl('/api/activity')).then(function(r){return r.json();});
  Promise.all([p1,p2,p3]).then(function(results){
    statsData=results[0];toolsData=results[1];activityData=results[2];
    setStatus('ok');refreshUI();
  }).catch(function(err){
    console.error('Dashboard fetch error:',err);setStatus('error');
  });
}

// Event handlers
document.getElementById('window-select').addEventListener('change',function(){
  windowHours=parseInt(this.value,10);fetchAll();
});
document.getElementById('refresh-select').addEventListener('change',function(){
  refreshMs=parseInt(this.value,10);
  if(refreshTimer)clearInterval(refreshTimer);
  if(refreshMs>0)refreshTimer=setInterval(fetchAll,refreshMs);
});

// Initial load
fetchAll();
refreshTimer=setInterval(fetchAll,refreshMs);

// Redraw on resize
var resizeTimer;
window.addEventListener('resize',function(){
  clearTimeout(resizeTimer);resizeTimer=setTimeout(function(){if(statsData)refreshUI();},300);
});

})();
</script>
</body>
</html>"""
