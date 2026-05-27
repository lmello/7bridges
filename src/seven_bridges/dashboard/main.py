# ruff: noqa: E501, SIM105
# E501: dashboard HTML/CSS/JS is intentionally compact.
# SIM105: try/except in the JS string is not Python code.
"""FastAPI dashboard application for 7-bridges usage metrics."""

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from .reader import compute_stats

app = FastAPI(title="7 Bridges Dashboard", version="0.2.0")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats")
def api_stats(hours: int = Query(default=24, ge=1, le=168)) -> JSONResponse:
    """Return aggregated dashboard statistics as JSON."""
    stats = compute_stats(hours=hours)
    return JSONResponse(content=stats)


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
<style>
*, *::before, *::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;background:#0d1117;color:#c9d1d9;line-height:1.5;min-height:100vh}
a{color:#d4a5ff;text-decoration:none}
a:hover{text-decoration:underline}

/* Layout */
header{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;position:sticky;top:0;z-index:10}
.header-left{display:flex;align-items:center;gap:12px}
.header-left svg{color:#d4a5ff}
.header-left h1{font-size:1.25rem;font-weight:600;color:#f0f6fc;letter-spacing:-0.02em}
.header-right{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.filter-pills{display:flex;gap:6px;flex-wrap:wrap}
.pill{background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:20px;padding:4px 14px;font-size:0.8rem;cursor:pointer;transition:all 0.15s ease;white-space:nowrap;font-family:inherit}
.pill:hover{background:#30363d;border-color:#d4a5ff}
.pill.active{background:#d4a5ff20;border-color:#d4a5ff;color:#d4a5ff;font-weight:600}
.updated{display:flex;align-items:center;gap:6px;font-size:0.78rem;color:#8b949e}
.updated .dot{width:8px;height:8px;border-radius:50%}
.updated .dot.ok{background:#3fb950}
.updated .dot.error{background:#f85149}
.updated .dot.fetching{background:#3fb950;animation:pulse 0.8s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
.updated .ts{font-variant-numeric:tabular-nums}

main{padding:24px;max-width:1440px;margin:0 auto}

/* Cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:24px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:18px 20px;transition:border-color 0.15s}
.card:hover{border-color:#d4a5ff40}
.card-label{font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;color:#8b949e;margin-bottom:4px}
.card-value{font-size:1.8rem;font-weight:700;color:#f0f6fc;line-height:1.2;font-variant-numeric:tabular-nums}
.card-sub{font-size:0.78rem;color:#8b949e;margin-top:4px}
.card.accent .card-value{color:#d4a5ff}
.card.success .card-value{color:#3fb950}
.card.warning .card-value{color:#d29922}
.card.danger .card-value{color:#f85149}

/* Charts section */
.charts-section{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:16px;margin-bottom:24px}
.chart-panel{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:18px 20px}
.chart-panel h2{font-size:0.9rem;font-weight:600;color:#c9d1d9;margin-bottom:12px}
.chart-wrap{position:relative;width:100%}
.chart-wrap canvas{width:100%;height:auto;display:block}
.chart-empty{display:flex;align-items:center;justify-content:center;height:200px;color:#484f58;font-size:0.85rem}

/* Tables */
.table-section{margin-bottom:24px}
.table-section h2{font-size:1rem;font-weight:600;color:#f0f6fc;margin-bottom:12px}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:0.82rem}
thead th{background:#161b22;border-bottom:2px solid #30363d;padding:10px 12px;text-align:left;color:#c9d1d9;font-weight:600;white-space:nowrap;cursor:pointer;user-select:none;position:sticky;top:0}
thead th:hover{color:#f0f6fc}
thead th .sort-arrow{font-size:0.7rem;margin-left:4px;opacity:0.5}
thead th.sorted .sort-arrow{opacity:1;color:#d4a5ff}
tbody td{padding:8px 12px;border-bottom:1px solid #21262d;white-space:nowrap}
tbody tr:hover{background:#1c2128}
tbody td.num{text-align:right;font-variant-numeric:tabular-nums}
.chip{display:inline-block;background:#d4a5ff20;color:#d4a5ff;border-radius:4px;padding:1px 8px;font-size:0.75rem;font-weight:500}

/* Accessible visually hidden */
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}

/* Footer */
footer{text-align:center;padding:16px;color:#484f58;font-size:0.75rem;border-top:1px solid #21262d}

@media(max-width:768px){
  header{padding:12px 16px}
  main{padding:16px}
  .cards{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
  .charts-section{grid-template-columns:1fr}
  .card-value{font-size:1.4rem}
}
</style>
</head>
<body>
<header>
  <div class="header-left">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 9V6a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-3"/><path d="M2 12h8l2 2 4-4"/></svg>
    <h1>7 Bridges Dashboard</h1>
  </div>
  <div class="header-right">
    <div class="filter-pills" id="filter-pills"></div>
    <div class="updated">
      <span class="dot ok" id="status-dot"></span>
      <span class="ts" id="last-updated">--</span>
    </div>
  </div>
</header>
<main>
  <div class="cards" id="cards"></div>
  <div class="charts-section">
    <div class="chart-panel">
      <h2>Requests / Hour</h2>
      <div class="chart-wrap"><canvas id="chart-reqs" role="img" aria-label="Bar chart of requests per hour"></canvas></div>
      <div class="sr-only" id="chart-reqs-table"></div>
      <div class="chart-empty" id="chart-reqs-empty" style="display:none">No data for the selected period</div>
    </div>
    <div class="chart-panel">
      <h2>Tokens / Hour</h2>
      <div class="chart-wrap"><canvas id="chart-tokens" role="img" aria-label="Stacked bar chart of input and output tokens per hour"></canvas></div>
      <div class="sr-only" id="chart-tokens-table"></div>
      <div class="chart-empty" id="chart-tokens-empty" style="display:none">No data for the selected period</div>
    </div>
    <div class="chart-panel">
      <h2>Cost / Hour</h2>
      <div class="chart-wrap"><canvas id="chart-cost" role="img" aria-label="Bar chart of estimated cost per hour in USD"></canvas></div>
      <div class="sr-only" id="chart-cost-table"></div>
      <div class="chart-empty" id="chart-cost-empty" style="display:none">No data for the selected period</div>
    </div>
  </div>
  <div class="table-section">
    <h2>Backend Breakdown</h2>
    <div class="table-wrap"><table id="table-backend"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="table-section">
    <h2>Model Breakdown</h2>
    <div class="table-wrap"><table id="table-model"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="table-section">
    <h2>Top Sessions (by requests)</h2>
    <div class="table-wrap"><table id="table-session"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="table-section">
    <h2>Recent Errors</h2>
    <div class="table-wrap"><table id="table-errors"><thead></thead><tbody></tbody></table></div>
  </div>
  <div class="table-section">
    <h2>Recent Requests</h2>
    <div class="table-wrap"><table id="table-requests"><thead></thead><tbody></tbody></table></div>
  </div>
</main>
<footer>7 Bridges Dashboard &middot; Auto-refreshes every 10s</footer>

<script>
(function(){
"use strict";

/* ---- Utilities ---- */

function esc(s){
  var d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

function fmtNum(n){
  if (n == null) return '0';
  if (typeof n === 'number'){
    if (n < 10 && n === Math.floor(n)) return String(n);
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(Math.floor(n));
  }
  return String(n);
}

function fmtCost(n){
  if (n == null) return '$0.00';
  var v = Number(n);
  if (v < 0.01) return '<$0.01';
  if (v < 1) return '$' + v.toFixed(2);
  if (v < 1000) return '$' + v.toFixed(1);
  return '$' + (v / 1e3).toFixed(1) + 'K';
}

function fmtPct(n){
  if (n == null) return '0%';
  return Number(n).toFixed(1) + '%';
}

function fmtMs(n){
  if (n == null) return '--';
  var v = Number(n);
  if (v < 1000) return v.toFixed(0) + 'ms';
  return (v / 1000).toFixed(1) + 's';
}

function fmtTime(ts){
  if (!ts) return '--';
  try{
    var d = new Date(ts);
    return d.toLocaleString();
  }catch(e){
    return ts;
  }
}

/* ---- State ---- */

var activeBackends = [];
var allBackends = [];
var statsData = null;
var lastSort = {table: null, col: null, asc: true};

/* ---- Chart rendering (Canvas 2D) ---- */

function chartMax(data, defaultMax){
  if (!data || data.length === 0) return defaultMax;
  var m = 0;
  for (var i = 0; i < data.length; i++){
    if (data[i] > m) m = data[i];
  }
  if (m === 0) return defaultMax;
  // Round up to a nice number
  var mag = Math.pow(10, Math.floor(Math.log10(m)));
  var norm = m / mag;
  if (norm <= 1) return mag;
  if (norm <= 2) return 2 * mag;
  if (norm <= 5) return 5 * mag;
  return 10 * mag;
}

function drawBarChart(canvasId, data, valueKey, color, emptyId){
  var canvas = document.getElementById(canvasId);
  var empty = document.getElementById(emptyId);
  if (!canvas || !empty) return;

  var ctx = canvas.getContext('2d');
  var labels = data.labels || [];
  var values = data[valueKey] || [];
  var hasData = false;
  for (var i = 0; i < values.length; i++){ if (values[i] > 0){ hasData = true; break; } }

  if (!hasData || labels.length === 0){
    canvas.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }
  canvas.style.display = 'block';
  empty.style.display = 'none';

  // Set canvas size (2x for retina)
  var dpr = window.devicePixelRatio || 1;
  var rect = canvas.parentElement.getBoundingClientRect();
  var w = rect.width || 600;
  var h = 220;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.setTransform(1,0,0,1,0,0);
  ctx.scale(dpr, dpr);

  var pad = {top: 20, right: 10, bottom: 30, left: 60};
  var pw = w - pad.left - pad.right;
  var ph = h - pad.top - pad.bottom;

  // Background
  ctx.fillStyle = '#161b22';
  ctx.fillRect(0, 0, w, h);

  var maxVal = chartMax(values, 10);
  var barW = Math.max(2, (pw / labels.length) * 0.7);
  var gap = pw / labels.length;

  // Grid lines
  ctx.strokeStyle = '#21262d';
  ctx.lineWidth = 0.5;
  var gridLines = 4;
  for (var g = 0; g <= gridLines; g++){
    var y = pad.top + (ph / gridLines) * g;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = '#8b949e';
    ctx.font = '10px -apple-system,sans-serif';
    ctx.textAlign = 'right';
    var label = (maxVal / gridLines) * (gridLines - g);
    if (maxVal >= 1e6) label = (label / 1e6).toFixed(1) + 'M';
    else if (maxVal >= 1e3) label = (label / 1e3).toFixed(1) + 'K';
    else label = Math.round(label);
    ctx.fillText(String(label), pad.left - 6, y + 3);
  }

  // Bars
  for (var i = 0; i < labels.length; i++){
    var barH = (values[i] / maxVal) * ph;
    var x = pad.left + i * gap + (gap - barW) / 2;
    var y = pad.top + ph - barH;
    ctx.fillStyle = color;
    ctx.fillRect(x, y, barW, barH);

    // Show label for every nth bar to avoid crowding
    var showLabel = labels.length <= 12 || i % Math.ceil(labels.length / 6) === 0;
    if (showLabel){
      ctx.fillStyle = '#8b949e';
      ctx.font = '9px -apple-system,sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(labels[i], pad.left + i * gap + gap / 2, pad.top + ph + 14);
    }
  }

  // Axes
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + ph);
  ctx.lineTo(w - pad.right, pad.top + ph);
  ctx.stroke();
}

function drawStackedBarChart(canvasId, data, key1, key2, color1, color2, label1, label2, emptyId){
  var canvas = document.getElementById(canvasId);
  var empty = document.getElementById(emptyId);
  if (!canvas || !empty) return;

  var ctx = canvas.getContext('2d');
  var labels = data.labels || [];
  var values1 = data[key1] || [];
  var values2 = data[key2] || [];
  var hasData = false;
  for (var i = 0; i < values1.length; i++){ if (values1[i] > 0 || values2[i] > 0){ hasData = true; break; } }

  if (!hasData || labels.length === 0){
    canvas.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }
  canvas.style.display = 'block';
  empty.style.display = 'none';

  var dpr = window.devicePixelRatio || 1;
  var rect = canvas.parentElement.getBoundingClientRect();
  var w = rect.width || 600;
  var h = 220;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.setTransform(1,0,0,1,0,0);
  ctx.scale(dpr, dpr);

  var pad = {top: 20, right: 10, bottom: 30, left: 60};
  var pw = w - pad.left - pad.right;
  var ph = h - pad.top - pad.bottom;

  ctx.fillStyle = '#161b22';
  ctx.fillRect(0, 0, w, h);

  // Max is sum of both series
  var maxVal = 0;
  for (var i = 0; i < values1.length; i++){
    var s = values1[i] + values2[i];
    if (s > maxVal) maxVal = s;
  }
  maxVal = chartMax([maxVal], 10);

  var barW = Math.max(2, (pw / labels.length) * 0.7);
  var gap = pw / labels.length;

  // Grid
  ctx.strokeStyle = '#21262d';
  ctx.lineWidth = 0.5;
  var gridLines = 4;
  for (var g = 0; g <= gridLines; g++){
    var y = pad.top + (ph / gridLines) * g;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = '#8b949e';
    ctx.font = '10px -apple-system,sans-serif';
    ctx.textAlign = 'right';
    var lbl = (maxVal / gridLines) * (gridLines - g);
    if (maxVal >= 1e6) lbl = (lbl / 1e6).toFixed(1) + 'M';
    else if (maxVal >= 1e3) lbl = (lbl / 1e3).toFixed(1) + 'K';
    else lbl = Math.round(lbl);
    ctx.fillText(String(lbl), pad.left - 6, y + 3);
  }

  // Bars — stacked
  for (var i = 0; i < labels.length; i++){
    var x = pad.left + i * gap + (gap - barW) / 2;
    var h1 = (values1[i] / maxVal) * ph;
    var h2 = (values2[i] / maxVal) * ph;
    // Output (top)
    ctx.fillStyle = color2;
    ctx.fillRect(x, pad.top + ph - h1 - h2, barW, h2);
    // Input (bottom)
    ctx.fillStyle = color1;
    ctx.fillRect(x, pad.top + ph - h1, barW, h1);

    var showLabel = labels.length <= 12 || i % Math.ceil(labels.length / 6) === 0;
    if (showLabel){
      ctx.fillStyle = '#8b949e';
      ctx.font = '9px -apple-system,sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(labels[i], pad.left + i * gap + gap / 2, pad.top + ph + 14);
    }
  }

  // Axes
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + ph);
  ctx.lineTo(w - pad.right, pad.top + ph);
  ctx.stroke();

  // Legend
  var lx = pad.left + 10;
  var ly = pad.top - 2;
  ctx.fillStyle = color1;
  ctx.fillRect(lx, ly, 10, 10);
  ctx.fillStyle = '#c9d1d9';
  ctx.font = '10px -apple-system,sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(label1, lx + 14, ly + 9);

  ctx.fillStyle = color2;
  ctx.fillRect(lx + 60, ly, 10, 10);
  ctx.fillText(label2, lx + 74, ly + 9);
}

/* ---- Table rendering ---- */

var COL_DEFS = {
  backend: [
    {key:'backend', title:'Backend'},
    {key:'requests', title:'Requests', num:true, fmt:fmtNum},
    {key:'input_tokens', title:'Input Tokens', num:true, fmt:fmtNum},
    {key:'output_tokens', title:'Output Tokens', num:true, fmt:fmtNum},
    {key:'cost', title:'Cost', num:true, fmt:fmtCost},
    {key:'avg_latency_ms', title:'Avg Latency', num:true, fmt:fmtMs},
    {key:'errors', title:'Errors', num:true},
    {key:'error_rate', title:'Error Rate', num:true, fmt:fmtPct},
    {key:'cache_hit_rate', title:'Cache Hit Rate', num:true, fmt:fmtPct}
  ],
  model: [
    {key:'model_alias', title:'Model'},
    {key:'backend', title:'Backend'},
    {key:'requests', title:'Requests', num:true, fmt:fmtNum},
    {key:'input_tokens', title:'Input Tokens', num:true, fmt:fmtNum},
    {key:'output_tokens', title:'Output Tokens', num:true, fmt:fmtNum},
    {key:'cost', title:'Cost', num:true, fmt:fmtCost},
    {key:'avg_latency_ms', title:'Avg Latency', num:true, fmt:fmtMs}
  ],
  session: [
    {key:'session_id', title:'Session'},
    {key:'requests', title:'Requests', num:true, fmt:fmtNum},
    {key:'input_tokens', title:'Input Tokens', num:true, fmt:fmtNum},
    {key:'output_tokens', title:'Output Tokens', num:true, fmt:fmtNum},
    {key:'cost', title:'Cost', num:true, fmt:fmtCost},
    {key:'last_active', title:'Last Active', fmt:fmtTime}
  ],
  errors: [
    {key:'timestamp', title:'Time', fmt:fmtTime},
    {key:'bridge', title:'Backend'},
    {key:'model_alias', title:'Model'},
    {key:'status_code', title:'Status', num:true},
    {key:'error_type', title:'Error Type'},
    {key:'error_message', title:'Message'}
  ],
  requests: [
    {key:'timestamp', title:'Time', fmt:fmtTime},
    {key:'model_alias', title:'Model'},
    {key:'bridge', title:'Backend'},
    {key:'stream', title:'Stream'},
    {key:'estimated_cost_usd', title:'Cost', fmt:fmtCost},
    {key:'latency_ms', title:'Latency', fmt:fmtMs},
    {key:'session_id', title:'Session'}
  ]
};

function renderTable(tableId, columns, rows, defId){
  var table = document.getElementById(tableId);
  var thead = table.querySelector('thead');
  var tbody = table.querySelector('tbody');

  // Headers
  var hhtml = '<tr>';
  for (var i = 0; i < columns.length; i++){
    var col = columns[i];
    var arrow = '';
    if (lastSort.table === defId && lastSort.col === col.key){
      arrow = ' <span class="sort-arrow">' + (lastSort.asc ? '&#9650;' : '&#9660;') + '</span>';
    } else {
      arrow = ' <span class="sort-arrow">&#9650;&#9660;</span>';
    }
    var cls = (lastSort.table === defId && lastSort.col === col.key) ? ' sorted' : '';
    hhtml += '<th class="' + cls + '" data-col="' + esc(col.key) + '">' + esc(col.title) + arrow + '</th>';
  }
  hhtml += '</tr>';
  thead.innerHTML = hhtml;

  // Body
  var bhtml = '';
  for (var r = 0; r < rows.length; r++){
    bhtml += '<tr>';
    for (var c = 0; c < columns.length; c++){
      var col2 = columns[c];
      var val = rows[r][col2.key];
      var display = col2.fmt ? col2.fmt(val) : (val != null ? esc(String(val)) : '--');
      if (col2.key === 'stream'){
        display = val ? '<span class="chip">stream</span>' : '<span class="chip" style="background:#30363d;color:#8b949e">batch</span>';
      }
      var cls2 = col2.num ? 'num' : '';
      bhtml += '<td class="' + cls2 + '">' + display + '</td>';
    }
    bhtml += '</tr>';
  }
  tbody.innerHTML = bhtml;

  // Click handlers
  thead.querySelectorAll('th').forEach(function(th){
    th.addEventListener('click', function(){
      var colKey = th.getAttribute('data-col');
      sortTable(defId, colKey, columns, rows, tableId, thead);
    });
  });
}

function sortTable(defId, colKey, columns, rows, tableId, thead){
  if (lastSort.table === defId && lastSort.col === colKey){
    lastSort.asc = !lastSort.asc;
  } else {
    lastSort.table = defId;
    lastSort.col = colKey;
    lastSort.asc = true;
  }

  // Find column definition
  var colDef = null;
  for (var i = 0; i < columns.length; i++){
    if (columns[i].key === colKey){ colDef = columns[i]; break; }
  }
  var isNum = colDef && colDef.num;

  rows.sort(function(a, b){
    var va = a[colKey], vb = b[colKey];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (isNum){
      va = Number(va); vb = Number(vb);
    } else {
      va = String(va).toLowerCase(); vb = String(vb).toLowerCase();
    }
    if (va < vb) return lastSort.asc ? -1 : 1;
    if (va > vb) return lastSort.asc ? 1 : -1;
    return 0;
  });

  renderTable(tableId, columns, rows, defId);
}

/* ---- Build sr-only fallback tables for charts ---- */

function buildSrTable(containerId, columns, rows){
  var el = document.getElementById(containerId);
  if (!el) return;
  var h = '<table><caption>' + esc(containerId) + '</caption><thead><tr>';
  for (var i = 0; i < columns.length; i++) h += '<th>' + esc(columns[i]) + '</th>';
  h += '</tr></thead><tbody>';
  for (var r = 0; r < rows.length; r++){
    h += '<tr>';
    for (var c = 0; c < columns.length; c++) h += '<td>' + esc(rows[r][c]) + '</td>';
    h += '</tr>';
  }
  h += '</tbody></table>';
  el.innerHTML = h;
}

/* ---- Filter management ---- */

function buildFilterPills(){
  var container = document.getElementById('filter-pills');
  var html = '<button class="pill active" data-backend="all">All</button>';
  for (var i = 0; i < allBackends.length; i++){
    var b = allBackends[i];
    html += '<button class="pill" data-backend="' + esc(b) + '">' + esc(b.charAt(0).toUpperCase() + b.slice(1)) + '</button>';
  }
  container.innerHTML = html;

  container.querySelectorAll('.pill').forEach(function(btn){
    btn.addEventListener('click', function(){
      var bk = btn.getAttribute('data-backend');
      if (bk === 'all'){
        activeBackends = [];
        container.querySelectorAll('.pill').forEach(function(p){ p.classList.remove('active'); });
        btn.classList.add('active');
      } else {
        // Remove 'all'
        var allBtn = container.querySelector('[data-backend="all"]');
        if (allBtn) allBtn.classList.remove('active');
        if (activeBackends.indexOf(bk) >= 0){
          activeBackends = activeBackends.filter(function(b){ return b !== bk; });
          btn.classList.remove('active');
        } else {
          activeBackends.push(bk);
          btn.classList.add('active');
        }
        // If nothing selected, re-select 'all'
        if (activeBackends.length === 0){
          activeBackends = [];
          if (allBtn) allBtn.classList.add('active');
        }
      }
      refreshUI();
    });
  });
}

/* ---- Data filtering ---- */

function filterByBackend(data){
  if (activeBackends.length === 0) return data;
  return data.filter(function(d){
    if (d.backend) return activeBackends.indexOf(d.backend) >= 0;
    if (d.bridge) return activeBackends.indexOf(d.bridge) >= 0;
    return false;
  });
}

/* ---- Main refresh ---- */

function setStatus(state){
  var dot = document.getElementById('status-dot');
  dot.className = 'dot ' + state;
  var ts = document.getElementById('last-updated');
  var now = new Date();
  ts.textContent = 'Last updated: ' + now.toLocaleTimeString();
}

function refreshUI(){
  if (!statsData) return;
  var s = statsData;

  // Header cards
  var costPerReq = s.aggregates.total_requests > 0
    ? '$' + (s.aggregates.total_cost / s.aggregates.total_requests).toFixed(4)
    : '$0.00';
  var cards = [
    {cls:'', label:'Total Requests (24h)', value:fmtNum(s.aggregates.total_requests), sub:''},
    {cls:'', label:'Total Input Tokens', value:fmtNum(s.aggregates.total_input_tokens), sub:''},
    {cls:'', label:'Total Output Tokens', value:fmtNum(s.aggregates.total_output_tokens), sub:''},
    {cls:'accent', label:'Estimated Cost', value:fmtCost(s.aggregates.total_cost), sub:'avg ' + costPerReq + '/req'},
    {cls:'success', label:'Cache Hit Rate', value:fmtPct(s.aggregates.cache_hit_rate), sub:''},
    {cls:s.aggregates.error_rate > 5 ? 'danger' : 'warning', label:'Error Rate', value:fmtPct(s.aggregates.error_rate), sub:s.total_errors_24h + ' errors'}
  ];
  var cardsHtml = '';
  for (var i = 0; i < cards.length; i++){
    var c = cards[i];
    cardsHtml += '<div class="card ' + c.cls + '"><div class="card-label">' + esc(c.label) + '</div><div class="card-value">' + esc(c.value) + '</div>' + (c.sub ? '<div class="card-sub">' + esc(c.sub) + '</div>' : '') + '</div>';
  }
  document.getElementById('cards').innerHTML = cardsHtml;

  // Time series charts
  drawBarChart('chart-reqs', s.time_series, 'requests', '#d4a5ff', 'chart-reqs-empty');
  drawStackedBarChart('chart-tokens', s.time_series, 'tokens_in', 'tokens_out', '#3fb950', '#d29922', 'Input', 'Output', 'chart-tokens-empty');
  drawBarChart('chart-cost', s.time_series, 'cost', '#f0883e', 'chart-cost-empty');

  // SR fallback tables
  var srReqRows = [];
  for (var i = 0; i < s.time_series.labels.length; i++){
    srReqRows.push([s.time_series.labels[i], String(s.time_series.requests[i])]);
  }
  buildSrTable('chart-reqs-table', ['Hour', 'Requests'], srReqRows);

  var srTokRows = [];
  for (var i = 0; i < s.time_series.labels.length; i++){
    srTokRows.push([s.time_series.labels[i], String(s.time_series.tokens_in[i]), String(s.time_series.tokens_out[i])]);
  }
  buildSrTable('chart-tokens-table', ['Hour', 'Input Tokens', 'Output Tokens'], srTokRows);

  var srCostRows = [];
  for (var i = 0; i < s.time_series.labels.length; i++){
    srCostRows.push([s.time_series.labels[i], '$' + s.time_series.cost[i].toFixed(4)]);
  }
  buildSrTable('chart-cost-table', ['Hour', 'Cost'], srCostRows);

  // Filtered data for tables
  var filteredBackend = filterByBackend(s.by_backend);
  var filteredModel = filterByBackend(s.by_model);
  var filteredErrors = filterByBackend(s.recent_errors);
  var filteredRequests = filterByBackend(s.recent_requests);

  // Tables
  renderTable('table-backend', COL_DEFS.backend, filteredBackend, 'backend');
  renderTable('table-model', COL_DEFS.model, filteredModel, 'model');
  renderTable('table-session', COL_DEFS.session, s.by_session, 'session');
  renderTable('table-errors', COL_DEFS.errors, filteredErrors, 'errors');
  renderTable('table-requests', COL_DEFS.requests, filteredRequests, 'requests');

  // Collect all unique backends for filter pills (only build once)
  if (allBackends.length === 0 && s.by_backend.length > 0){
    for (var i = 0; i < s.by_backend.length; i++){
      allBackends.push(s.by_backend[i].backend);
    }
    buildFilterPills();
  }
}

function fetchStats(){
  setStatus('fetching');
  fetch('/api/stats')
    .then(function(r){ return r.json(); })
    .then(function(data){
      statsData = data;
      setStatus('ok');
      refreshUI();
    })
    .catch(function(err){
      console.error('Dashboard fetch error:', err);
      setStatus('error');
    });
}

// Initial fetch + auto-refresh
fetchStats();
setInterval(fetchStats, 10000);

// Redraw charts on resize
var resizeTimer;
window.addEventListener('resize', function(){
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(function(){
    if (statsData) refreshUI();
  }, 200);
});

})();
</script>
</body>
</html>"""
