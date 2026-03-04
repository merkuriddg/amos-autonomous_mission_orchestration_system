#!/bin/bash
set -e

C2_DIR=~/mos_ws/src/mos_c2_console/mos_c2_console
C2_SERVER="$C2_DIR/c2_server.py"
TEMPLATES="$C2_DIR/templates"

echo "============================================"
echo "  MOS — EW/SIGINT/CYBER Route Fix"
echo "============================================"
echo ""

# ── Step 1: Verify HTML files exist ──
echo "[1/4] Checking template files..."
MISSING=0
for PAGE in ew.html sigint.html cyber.html; do
  if [ -f "$TEMPLATES/$PAGE" ]; then
    echo "  ✅ $PAGE found"
  else
    echo "  ❌ $PAGE MISSING — will create"
    MISSING=1
  fi
done

# ── Step 2: Create any missing HTML files ──
if [ "$MISSING" -eq 1 ]; then
echo ""
echo "[2/4] Creating missing templates..."

# ── ew.html ──
if [ ! -f "$TEMPLATES/ew.html" ]; then
cat > "$TEMPLATES/ew.html" << 'EWHTML'
<!DOCTYPE html>
<html><head>
<title>MOS — EW/SIGINT Dashboard</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff88;font-family:'Courier New',monospace;overflow-x:hidden}
.nav{display:flex;gap:12px;padding:6px 15px;background:#0a0a0aee;border-bottom:1px solid #ff006644;font-size:11px;position:fixed;top:0;left:0;right:0;z-index:9999}
.nav a{color:#00ccff;text-decoration:none}.nav a:hover{color:#fff}.nav a.active{color:#ff0066;font-weight:bold}
.nav .brand{color:#ff0066;font-weight:bold;margin-right:8px}
.content{margin-top:30px;padding:10px}
h1{color:#ff0066;font-size:16px;padding:10px;border-bottom:1px solid #333}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:10px}
.panel{background:#111;border:1px solid #333;border-radius:4px;padding:10px}
.panel h2{color:#00ccff;font-size:13px;margin-bottom:8px;border-bottom:1px solid #222;padding-bottom:4px}
#spectrum-canvas{width:100%;height:150px;background:#000;border:1px solid #333;border-radius:4px}
#waterfall-canvas{width:100%;height:120px;background:#000;border:1px solid #333;border-radius:4px}
#ew-map{height:300px;border-radius:4px;border:1px solid #333}
.emitter-list{max-height:250px;overflow-y:auto;font-size:11px}
.emitter-row{display:flex;justify-content:space-between;padding:3px 5px;border-bottom:1px solid #1a1a1a}
.emitter-row:hover{background:#1a1a1a}
.threat-high{color:#ff0044}.threat-med{color:#ffaa00}.threat-low{color:#00ff88}
.tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:bold}
.tag-hostile{background:#ff004433;color:#ff0044;border:1px solid #ff0044}
.tag-jammer{background:#ffaa0033;color:#ffaa00;border:1px solid #ffaa00}
.tag-drone{background:#ff006633;color:#ff0066;border:1px solid #ff0066}
.tag-unknown{background:#66666633;color:#999;border:1px solid #666}
.stat-bar{display:flex;gap:15px;padding:8px 10px;background:#111;border:1px solid #333;margin:10px;border-radius:4px;font-size:12px}
.stat-bar span{color:#888}.stat-bar strong{color:#00ff88}
.alert-feed{max-height:150px;overflow-y:auto;font-size:11px}
.alert-row{padding:3px 5px;border-left:3px solid #ff0044;margin-bottom:3px;background:#1a0000}
canvas{image-rendering:pixelated}
</style>
</head><body>
<div class="nav">
  <span class="brand">MOS</span>
  <a href="/">C2 Map</a>
  <a href="/dashboard">Digital Twin</a>
  <a class="active" href="/ew">⚡ EW/SIGINT</a>
  <a href="/sigint">📡 SIGINT DB</a>
  <a href="/cyber">🔓 Cyber</a>
  <a href="/awacs">AWACS</a>
  <a href="/tactical3d">3D</a>
  <a href="/echelon">Echelon</a>
  <a href="/hal">HAL</a>
</div>

<div class="content">
<h1>⚡ EW / SIGINT DASHBOARD <span style="float:right;color:#888;font-size:12px" id="clock"></span></h1>

<div class="stat-bar">
  <span>EMITTERS: <strong id="emitter-count">0</strong></span>
  <span>HOSTILE: <strong style="color:#ff0044" id="hostile-count">0</strong></span>
  <span>JAMMERS: <strong style="color:#ffaa00" id="jammer-count">0</strong></span>
  <span>RF POLICY: <strong style="color:#00ccff" id="rf-policy">PERMISSIVE</strong></span>
  <span>SDR: <strong style="color:#00ff88" id="sdr-status">SIMULATED</strong></span>
</div>

<div class="panel" style="margin:10px">
  <h2>📊 SPECTRUM ANALYZER (400–500 MHz)</h2>
  <canvas id="spectrum-canvas"></canvas>
</div>

<div class="grid">
  <div>
    <div class="panel">
      <h2>📍 EMITTER MAP</h2>
      <div id="ew-map"></div>
    </div>
    <div class="panel" style="margin-top:10px">
      <h2>🌊 WATERFALL</h2>
      <canvas id="waterfall-canvas"></canvas>
    </div>
  </div>
  <div>
    <div class="panel">
      <h2>📡 DETECTED EMITTERS</h2>
      <div class="emitter-list" id="emitter-list"></div>
    </div>
    <div class="panel" style="margin-top:10px">
      <h2>🚨 EW ALERTS</h2>
      <div class="alert-feed" id="alert-feed"></div>
    </div>
  </div>
</div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
// ── Clock ──
setInterval(()=>{document.getElementById('clock').textContent=new Date().toISOString().replace('T',' ').split('.')[0]+'Z'},1000);

// ── Map ──
const map=L.map('ew-map',{zoomControl:false}).setView([27.85,-82.5],11);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{maxZoom:19}).addTo(map);
const emitterMarkers={};

// ── Spectrum Canvas ──
const specCanvas=document.getElementById('spectrum-canvas');
const specCtx=specCanvas.getContext('2d');
function resizeSpec(){specCanvas.width=specCanvas.clientWidth;specCanvas.height=specCanvas.clientHeight}
resizeSpec();window.addEventListener('resize',resizeSpec);

// ── Waterfall Canvas ──
const wfCanvas=document.getElementById('waterfall-canvas');
const wfCtx=wfCanvas.getContext('2d');
function resizeWf(){wfCanvas.width=wfCanvas.clientWidth;wfCanvas.height=wfCanvas.clientHeight}
resizeWf();window.addEventListener('resize',resizeWf);
let wfRow=0;

// ── Generate simulated spectrum ──
function genSpectrum(bins=512){
  const d=new Array(bins);
  for(let i=0;i<bins;i++){d[i]=-90+Math.random()*10}
  // inject some signals
  const sigs=[{bin:64,w:8,p:-30},{bin:180,w:4,p:-40},{bin:300,w:12,p:-25},{bin:420,w:6,p:-45}];
  sigs.forEach(s=>{for(let j=-s.w;j<=s.w;j++){const idx=s.bin+j;if(idx>=0&&idx<bins){d[idx]=s.p+Math.random()*5-Math.abs(j)*3}}});
  return d;
}

// ── Draw Spectrum ──
function drawSpectrum(data){
  const W=specCanvas.width,H=specCanvas.height;
  specCtx.fillStyle='#000';specCtx.fillRect(0,0,W,H);
  // grid
  specCtx.strokeStyle='#1a1a1a';specCtx.lineWidth=1;
  for(let y=0;y<H;y+=H/5){specCtx.beginPath();specCtx.moveTo(0,y);specCtx.lineTo(W,y);specCtx.stroke()}
  // spectrum line
  specCtx.beginPath();specCtx.strokeStyle='#00ff88';specCtx.lineWidth=1.5;
  data.forEach((v,i)=>{
    const x=(i/data.length)*W;
    const y=H-((v+100)/80)*H;
    i===0?specCtx.moveTo(x,y):specCtx.lineTo(x,y);
  });
  specCtx.stroke();
  // fill
  specCtx.lineTo(W,H);specCtx.lineTo(0,H);specCtx.closePath();
  specCtx.fillStyle='rgba(0,255,136,0.05)';specCtx.fill();
  // labels
  specCtx.fillStyle='#666';specCtx.font='10px monospace';
  specCtx.fillText('400 MHz',5,H-5);specCtx.fillText('500 MHz',W-55,H-5);
  specCtx.fillText('-20 dBm',5,15);specCtx.fillText('-100 dBm',5,H-15);
}

// ── Draw Waterfall Row ──
function drawWaterfall(data){
  const W=wfCanvas.width,H=wfCanvas.height;
  // scroll down
  const img=wfCtx.getImageData(0,0,W,H-1);
  wfCtx.putImageData(img,0,1);
  // draw new row at top
  data.forEach((v,i)=>{
    const x=Math.floor((i/data.length)*W);
    const norm=Math.max(0,Math.min(1,(v+100)/70));
    const r=Math.floor(norm*255);
    const g=Math.floor(norm*128);
    const b=Math.floor((1-norm)*50);
    wfCtx.fillStyle=`rgb(${r},${g},${b})`;
    wfCtx.fillRect(x,0,Math.ceil(W/data.length)+1,1);
  });
}

// ── Simulated Emitters ──
const simEmitters=[];
const classes=['HOSTILE','JAMMER','DRONE_C2','UNKNOWN','FRIENDLY','SUSPECT'];
const types=['RADAR','COMMS','GPS_JAMMER','DRONE_C2','WIFI','CELL'];
for(let i=0;i<12;i++){
  simEmitters.push({
    id:'EMT-'+String(i).padStart(4,'0'),
    lat:27.8+(Math.random()-0.5)*0.15,
    lon:-82.5+(Math.random()-0.5)*0.2,
    freq:(400+Math.random()*100).toFixed(1),
    power:(-30-Math.random()*50).toFixed(0),
    classification:classes[Math.floor(Math.random()*classes.length)],
    type:types[Math.floor(Math.random()*types.length)],
    threat:(Math.random()).toFixed(2),
    active:Math.random()>0.3
  });
}

function updateEmitters(){
  const list=document.getElementById('emitter-list');
  list.innerHTML='';
  let hostile=0,jammers=0;
  simEmitters.forEach(e=>{
    if(!e.active)return;
    // slight position drift
    e.lat+=((Math.random()-0.5)*0.001);
    e.lon+=((Math.random()-0.5)*0.001);
    e.power=(-30-Math.random()*50).toFixed(0);

    const cls=e.classification.toLowerCase();
    const tagClass=cls.includes('hostile')?'tag-hostile':cls.includes('jam')?'tag-jammer':cls.includes('drone')?'tag-drone':'tag-unknown';
    const threatClass=e.threat>0.7?'threat-high':e.threat>0.4?'threat-med':'threat-low';

    if(cls.includes('hostile'))hostile++;
    if(cls.includes('jam'))jammers++;

    list.innerHTML+=`<div class="emitter-row">
      <span>${e.id}</span>
      <span class="tag ${tagClass}">${e.classification}</span>
      <span>${e.freq} MHz</span>
      <span>${e.power} dBm</span>
      <span class="${threatClass}">${e.threat}</span>
    </div>`;

    // map markers
    if(emitterMarkers[e.id]){
      emitterMarkers[e.id].setLatLng([e.lat,e.lon]);
    }else{
      const color=cls.includes('hostile')?'#ff0044':cls.includes('jam')?'#ffaa00':'#00ff88';
      emitterMarkers[e.id]=L.circleMarker([e.lat,e.lon],{radius:6,color:color,fillColor:color,fillOpacity:0.6,weight:1}).addTo(map).bindPopup(`<b>${e.id}</b><br>${e.classification}<br>${e.freq} MHz`);
    }
  });
  document.getElementById('emitter-count').textContent=simEmitters.filter(e=>e.active).length;
  document.getElementById('hostile-count').textContent=hostile;
  document.getElementById('jammer-count').textContent=jammers;
}

// ── Alert feed ──
const alertMsgs=['GPS interference detected near ALPHA sector','New emitter classified as HOSTILE','Jammer activity on 1575 MHz','Drone C2 link detected 915 MHz','Deconfliction warning: friendly near jammer zone','SIGINT intercept — unencrypted COMMS','Spectrum anomaly band 460-465 MHz'];
let alertIdx=0;
function addAlert(){
  const feed=document.getElementById('alert-feed');
  const ts=new Date().toISOString().split('T')[1].split('.')[0];
  const msg=alertMsgs[alertIdx%alertMsgs.length];
  feed.innerHTML=`<div class="alert-row">[${ts}] ${msg}</div>`+feed.innerHTML;
  if(feed.children.length>30)feed.removeChild(feed.lastChild);
  alertIdx++;
}

// ── Main Loop ──
setInterval(()=>{
  const data=genSpectrum();
  drawSpectrum(data);
  drawWaterfall(data);
},200);
setInterval(updateEmitters,2000);
setInterval(addAlert,4000);
updateEmitters();
</script>
</body></html>
EWHTML
echo "  ✅ ew.html created"
fi

# ── sigint.html ──
if [ ! -f "$TEMPLATES/sigint.html" ]; then
cat > "$TEMPLATES/sigint.html" << 'SIGHTML'
<!DOCTYPE html>
<html><head>
<title>MOS — SIGINT Database</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff88;font-family:'Courier New',monospace}
.nav{display:flex;gap:12px;padding:6px 15px;background:#0a0a0aee;border-bottom:1px solid #ff006644;font-size:11px;position:fixed;top:0;left:0;right:0;z-index:9999}
.nav a{color:#00ccff;text-decoration:none}.nav a:hover{color:#fff}.nav a.active{color:#ff0066;font-weight:bold}
.nav .brand{color:#ff0066;font-weight:bold;margin-right:8px}
.content{margin-top:30px;padding:10px}
h1{color:#ff0066;font-size:16px;padding:10px;border-bottom:1px solid #333}
.filters{display:flex;gap:8px;padding:10px;flex-wrap:wrap}
.fbtn{padding:4px 12px;background:#1a1a1a;border:1px solid #333;color:#888;cursor:pointer;border-radius:3px;font-family:inherit;font-size:11px}
.fbtn:hover,.fbtn.active{background:#ff006633;color:#ff0066;border-color:#ff0066}
.grid2{display:grid;grid-template-columns:2fr 1fr;gap:10px;padding:10px}
.panel{background:#111;border:1px solid #333;border-radius:4px;padding:10px}
.panel h2{color:#00ccff;font-size:13px;margin-bottom:8px;border-bottom:1px solid #222;padding-bottom:4px}
table{width:100%;border-collapse:collapse;font-size:11px}
th{text-align:left;color:#888;padding:4px;border-bottom:1px solid #333}
td{padding:4px;border-bottom:1px solid #1a1a1a}
tr:hover{background:#1a1a1a;cursor:pointer}
tr.selected{background:#ff006622}
.tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:bold}
.tag-hostile{background:#ff004433;color:#ff0044}.tag-jammer{background:#ffaa0033;color:#ffaa00}
.tag-drone{background:#ff006633;color:#ff0066}.tag-unknown{background:#33333366;color:#888}
.tag-friendly{background:#00ff8833;color:#00ff88}
#waveform{width:100%;height:100px;background:#000;border:1px solid #333;border-radius:4px}
.detail-row{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1a1a1a;font-size:11px}
.detail-row .lbl{color:#888}
.tools{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.tool{padding:3px 8px;background:#0a2a1a;border:1px solid #00ff8844;color:#00ff88;border-radius:3px;font-size:10px}
</style>
</head><body>
<div class="nav">
  <span class="brand">MOS</span>
  <a href="/">C2 Map</a>
  <a href="/dashboard">Digital Twin</a>
  <a href="/ew">⚡ EW/SIGINT</a>
  <a class="active" href="/sigint">📡 SIGINT DB</a>
  <a href="/cyber">🔓 Cyber</a>
  <a href="/awacs">AWACS</a>
  <a href="/tactical3d">3D</a>
  <a href="/echelon">Echelon</a>
  <a href="/hal">HAL</a>
</div>
<div class="content">
<h1>📡 SIGINT DATABASE <span style="float:right;color:#888;font-size:12px" id="clock"></span></h1>
<div class="filters">
  <button class="fbtn active" onclick="filter('ALL')">ALL</button>
  <button class="fbtn" onclick="filter('HOSTILE')">HOSTILE</button>
  <button class="fbtn" onclick="filter('JAMMER')">JAMMER</button>
  <button class="fbtn" onclick="filter('DRONE_C2')">DRONE C2</button>
  <button class="fbtn" onclick="filter('FRIENDLY')">FRIENDLY</button>
  <button class="fbtn" onclick="filter('UNKNOWN')">UNKNOWN</button>
</div>
<div class="grid2">
  <div class="panel">
    <h2>SIGNAL DATABASE (<span id="sig-count">0</span> signals)</h2>
    <table><thead><tr><th>ID</th><th>CLASS</th><th>TYPE</th><th>FREQ</th><th>PWR</th><th>MOD</th><th>THREAT</th><th>FIRST SEEN</th></tr></thead>
    <tbody id="sig-table"></tbody></table>
  </div>
  <div>
    <div class="panel">
      <h2>🔍 SIGNAL DETAIL</h2>
      <div id="detail-info"><span style="color:#666">Select a signal...</span></div>
      <canvas id="waveform" style="margin-top:8px"></canvas>
      <div class="panel" style="margin-top:10px;border:1px solid #222">
        <h2>🛠 RECOMMENDED TOOLS</h2>
        <div class="tools" id="tools">
          <span class="tool">GNU Radio</span><span class="tool">URH</span><span class="tool">inspectrum</span>
        </div>
      </div>
    </div>
  </div>
</div>
</div>
<script>
setInterval(()=>{document.getElementById('clock').textContent=new Date().toISOString().replace('T',' ').split('.')[0]+'Z'},1000);
const mods=['FHSS','DSSS','OFDM','FM','AM','QAM','PSK','FSK','CHIRP'];
const classes=['HOSTILE','JAMMER','DRONE_C2','UNKNOWN','FRIENDLY'];
const types=['RADAR','COMMS','GPS_JAMMER','DRONE_C2','WIFI','CELL','SAT_LINK','DATA_LINK'];
const signals=[];
for(let i=0;i<25;i++){
  const cl=classes[Math.floor(Math.random()*classes.length)];
  signals.push({id:'SIG-'+String(i).padStart(4,'0'),classification:cl,type:types[Math.floor(Math.random()*types.length)],
    freq:(200+Math.random()*5600).toFixed(1),power:(-20-Math.random()*60).toFixed(0),
    modulation:mods[Math.floor(Math.random()*mods.length)],threat:(Math.random()).toFixed(2),
    firstSeen:new Date(Date.now()-Math.random()*3600000).toISOString().split('T')[1].split('.')[0],
    bandwidth:(0.1+Math.random()*20).toFixed(1)});
}
let currentFilter='ALL';
function filter(f){currentFilter=f;document.querySelectorAll('.fbtn').forEach(b=>{b.classList.toggle('active',b.textContent===f)});render()}
function render(){
  const tb=document.getElementById('sig-table');
  const filtered=currentFilter==='ALL'?signals:signals.filter(s=>s.classification===currentFilter||s.type===currentFilter);
  document.getElementById('sig-count').textContent=filtered.length;
  tb.innerHTML=filtered.map((s,i)=>{
    const cls=s.classification.toLowerCase();
    const tc=cls.includes('hostile')?'tag-hostile':cls.includes('jam')?'tag-jammer':cls.includes('drone')?'tag-drone':cls.includes('friend')?'tag-friendly':'tag-unknown';
    return `<tr onclick="selectSig(${signals.indexOf(s)})"><td>${s.id}</td><td><span class="tag ${tc}">${s.classification}</span></td><td>${s.type}</td><td>${s.freq} MHz</td><td>${s.power} dBm</td><td>${s.modulation}</td><td>${s.threat}</td><td>${s.firstSeen}</td></tr>`;
  }).join('');
}
function selectSig(idx){
  const s=signals[idx];
  document.getElementById('detail-info').innerHTML=
    `<div class="detail-row"><span class="lbl">ID</span><span>${s.id}</span></div>
     <div class="detail-row"><span class="lbl">Classification</span><span>${s.classification}</span></div>
     <div class="detail-row"><span class="lbl">Type</span><span>${s.type}</span></div>
     <div class="detail-row"><span class="lbl">Frequency</span><span>${s.freq} MHz</span></div>
     <div class="detail-row"><span class="lbl">Power</span><span>${s.power} dBm</span></div>
     <div class="detail-row"><span class="lbl">Modulation</span><span>${s.modulation}</span></div>
     <div class="detail-row"><span class="lbl">Bandwidth</span><span>${s.bandwidth} MHz</span></div>
     <div class="detail-row"><span class="lbl">Threat Score</span><span style="color:${s.threat>0.7?'#ff0044':s.threat>0.4?'#ffaa00':'#00ff88'}">${s.threat}</span></div>`;
  drawWaveform(s);
}
function drawWaveform(s){
  const c=document.getElementById('waveform');const ctx=c.getContext('2d');
  c.width=c.clientWidth;c.height=c.clientHeight;
  ctx.fillStyle='#000';ctx.fillRect(0,0,c.width,c.height);
  ctx.strokeStyle='#00ff88';ctx.lineWidth=1;ctx.beginPath();
  const freq=parseFloat(s.freq)/100;
  for(let x=0;x<c.width;x++){
    const y=c.height/2+Math.sin(x*freq*0.1)*30+Math.sin(x*0.02)*10+(Math.random()-0.5)*8;
    x===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
  }
  ctx.stroke();
}
render();
</script>
</body></html>
SIGHTML
echo "  ✅ sigint.html created"
fi

# ── cyber.html ──
if [ ! -f "$TEMPLATES/cyber.html" ]; then
cat > "$TEMPLATES/cyber.html" << 'CYBERHTML'
<!DOCTYPE html>
<html><head>
<title>MOS — Cyber Operations</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0a;color:#00ff88;font-family:'Courier New',monospace}
.nav{display:flex;gap:12px;padding:6px 15px;background:#0a0a0aee;border-bottom:1px solid #ff006644;font-size:11px;position:fixed;top:0;left:0;right:0;z-index:9999}
.nav a{color:#00ccff;text-decoration:none}.nav a:hover{color:#fff}.nav a.active{color:#ff0066;font-weight:bold}
.nav .brand{color:#ff0066;font-weight:bold;margin-right:8px}
.content{margin-top:30px;padding:10px}
h1{color:#ff0066;font-size:16px;padding:10px;border-bottom:1px solid #333}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;padding:10px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:0 10px 10px}
.panel{background:#111;border:1px solid #333;border-radius:4px;padding:10px}
.panel h2{color:#00ccff;font-size:13px;margin-bottom:8px;border-bottom:1px solid #222;padding-bottom:4px}
.stat-bar{display:flex;gap:15px;padding:8px 10px;background:#111;border:1px solid #333;margin:10px;border-radius:4px;font-size:12px}
.stat-bar span{color:#888}.stat-bar strong{color:#00ff88}
table{width:100%;border-collapse:collapse;font-size:11px}
th{text-align:left;color:#888;padding:4px;border-bottom:1px solid #333}
td{padding:4px;border-bottom:1px solid #1a1a1a}
tr:hover{background:#1a1a1a}
.sev-crit{color:#ff0044;font-weight:bold}.sev-high{color:#ff6600}.sev-med{color:#ffaa00}.sev-low{color:#00ff88}
.wifi-item{padding:6px;border-bottom:1px solid #1a1a1a;display:flex;justify-content:space-between;align-items:center}
.wifi-item:hover{background:#1a1a1a}
.wifi-bars{display:flex;gap:2px;align-items:flex-end}
.wifi-bar{width:3px;background:#00ff88;border-radius:1px}
.ids-alert{padding:5px;border-left:3px solid #ff0044;margin-bottom:4px;background:#1a0000;font-size:11px}
.ids-alert.warn{border-color:#ffaa00;background:#1a1a00}
</style>
</head><body>
<div class="nav">
  <span class="brand">MOS</span>
  <a href="/">C2 Map</a>
  <a href="/dashboard">Digital Twin</a>
  <a href="/ew">⚡ EW/SIGINT</a>
  <a href="/sigint">📡 SIGINT DB</a>
  <a class="active" href="/cyber">🔓 Cyber</a>
  <a href="/awacs">AWACS</a>
  <a href="/tactical3d">3D</a>
  <a href="/echelon">Echelon</a>
  <a href="/hal">HAL</a>
</div>
<div class="content">
<h1>🔓 CYBER OPERATIONS CENTER <span style="float:right;color:#888;font-size:12px" id="clock"></span></h1>
<div class="stat-bar">
  <span>NETWORKS: <strong id="net-count">0</strong></span>
  <span>HOSTS: <strong id="host-count">0</strong></span>
  <span>VULNS: <strong style="color:#ff0044" id="vuln-count">0</strong></span>
  <span>IDS ALERTS: <strong style="color:#ffaa00" id="ids-count">0</strong></span>
  <span>MODE: <strong style="color:#00ccff">PASSIVE RECON</strong></span>
</div>
<div class="grid3">
  <div class="panel">
    <h2>📶 WiFi Networks</h2>
    <div id="wifi-list"></div>
  </div>
  <div class="panel">
    <h2>🖥 Discovered Devices</h2>
    <table><thead><tr><th>IP</th><th>TYPE</th><th>OS</th><th>PORTS</th></tr></thead>
    <tbody id="device-table"></tbody></table>
  </div>
  <div class="panel">
    <h2>🛡 IDS Alerts</h2>
    <div id="ids-feed" style="max-height:300px;overflow-y:auto"></div>
  </div>
</div>
<div class="grid2">
  <div class="panel">
    <h2>🔴 VULNERABILITIES</h2>
    <table><thead><tr><th>CVE</th><th>SEVERITY</th><th>DESCRIPTION</th><th>HOST</th></tr></thead>
    <tbody id="vuln-table"></tbody></table>
  </div>
  <div class="panel">
    <h2>📊 NETWORK TOPOLOGY</h2>
    <canvas id="topo-canvas" style="width:100%;height:250px;background:#000;border:1px solid #333;border-radius:4px"></canvas>
  </div>
</div>
</div>
<script>
setInterval(()=>{document.getElementById('clock').textContent=new Date().toISOString().replace('T',' ').split('.')[0]+'Z'},1000);

// WiFi networks
const wifis=[
  {ssid:'DJI-PHANTOM-C2',enc:'WPA2',ch:6,sig:-45,suspicious:true},
  {ssid:'OPSNET-ALPHA',enc:'WPA3-ENT',ch:36,sig:-55,suspicious:false},
  {ssid:'ATT-WIFI-2G',enc:'WPA2',ch:11,sig:-70,suspicious:false},
  {ssid:'HIDDEN_NET',enc:'WPA2',ch:1,sig:-60,suspicious:true},
  {ssid:'MOS-MESH-01',enc:'WPA3',ch:149,sig:-40,suspicious:false},
  {ssid:'DRONE-LINK-915',enc:'OPEN',ch:3,sig:-50,suspicious:true},
];
function renderWifi(){
  const list=document.getElementById('wifi-list');
  document.getElementById('net-count').textContent=wifis.length;
  list.innerHTML=wifis.map(w=>{
    const bars=Math.min(4,Math.floor((w.sig+90)/12)+1);
    const barsHtml=Array.from({length:4},(_, i)=>`<div class="wifi-bar" style="height:${(i+1)*5}px;opacity:${i<bars?1:0.2}"></div>`).join('');
    return `<div class="wifi-item">
      <div><span style="color:${w.suspicious?'#ff0044':'#00ff88'}">${w.suspicious?'⚠':'✓'} ${w.ssid}</span><br>
      <span style="color:#666;font-size:10px">${w.enc} · Ch${w.ch} · ${w.sig} dBm</span></div>
      <div class="wifi-bars">${barsHtml}</div></div>`;
  }).join('');
}
renderWifi();

// Devices
const devices=[
  {ip:'10.0.1.42',type:'Drone',os:'Linux 5.4',ports:'22, 80, 14550'},
  {ip:'10.0.1.15',type:'UGV',os:'Ubuntu 22',ports:'22, 11311, 7400'},
  {ip:'10.0.2.7',type:'Router',os:'RouterOS 7',ports:'80, 443, 8291'},
  {ip:'10.0.2.50',type:'Camera',os:'Embedded',ports:'80, 554'},
  {ip:'10.0.3.15',type:'Unknown',os:'Unknown',ports:'22, 8080'},
  {ip:'10.0.1.100',type:'GCS',os:'Win 11',ports:'3389, 14550'},
  {ip:'10.0.1.88',type:'USV',os:'Linux 5.15',ports:'22, 80, 9090'},
];
document.getElementById('host-count').textContent=devices.length;
document.getElementById('device-table').innerHTML=devices.map(d=>
  `<tr><td style="color:#00ccff">${d.ip}</td><td>${d.type}</td><td>${d.os}</td><td>${d.ports}</td></tr>`).join('');

// Vulns
const vulns=[
  {cve:'CVE-2024-0005',sev:'CRITICAL',desc:'MAVLink No Auth — command injection',host:'10.0.1.42'},
  {cve:'CVE-2024-0006',sev:'HIGH',desc:'DDS Open Discovery — topic enumeration',host:'10.0.1.15'},
  {cve:'CVE-2024-0012',sev:'CRITICAL',desc:'RTSP unauthenticated stream access',host:'10.0.2.50'},
  {cve:'CVE-2024-0019',sev:'MEDIUM',desc:'Default credentials on web interface',host:'10.0.2.7'},
  {cve:'CVE-2024-0023',sev:'HIGH',desc:'Open telemetry port — data exfil risk',host:'10.0.1.88'},
];
document.getElementById('vuln-count').textContent=vulns.length;
document.getElementById('vuln-table').innerHTML=vulns.map(v=>{
  const sc=v.sev==='CRITICAL'?'sev-crit':v.sev==='HIGH'?'sev-high':v.sev==='MEDIUM'?'sev-med':'sev-low';
  return `<tr><td>${v.cve}</td><td class="${sc}">${v.sev}</td><td>${v.desc}</td><td style="color:#00ccff">${v.host}</td></tr>`;
}).join('');

// IDS Alerts
const idsAlerts=[
  {sev:'CRIT',msg:'Deauth flood detected on Ch 6 — possible WiFi jamming'},
  {sev:'HIGH',msg:'Port scan from 10.0.3.15 → 10.0.1.0/24'},
  {sev:'HIGH',msg:'MAVLink COMMAND_LONG from unauthorized source 10.0.3.15'},
  {sev:'WARN',msg:'ARP spoofing attempt detected on VLAN 10'},
  {sev:'CRIT',msg:'Unencrypted telemetry stream on port 14550'},
  {sev:'WARN',msg:'DNS query to known C2 domain from 10.0.3.15'},
];
document.getElementById('ids-count').textContent=idsAlerts.length;
const idsFeed=document.getElementById('ids-feed');
idsAlerts.forEach(a=>{
  const ts=new Date().toISOString().split('T')[1].split('.')[0];
  idsFeed.innerHTML+=`<div class="ids-alert ${a.sev==='WARN'?'warn':''}">[${ts}] <strong>${a.sev}</strong> — ${a.msg}</div>`;
});

// Simple topology canvas
const tc=document.getElementById('topo-canvas');
const tctx=tc.getContext('2d');
function drawTopo(){
  tc.width=tc.clientWidth;tc.height=tc.clientHeight;
  tctx.fillStyle='#000';tctx.fillRect(0,0,tc.width,tc.height);
  const cx=tc.width/2,cy=tc.height/2;
  // Gateway
  tctx.fillStyle='#ff0066';tctx.beginPath();tctx.arc(cx,cy,12,0,Math.PI*2);tctx.fill();
  tctx.fillStyle='#fff';tctx.font='9px monospace';tctx.fillText('GW',cx-8,cy+3);
  // Devices in circle
  devices.forEach((d,i)=>{
    const angle=(i/devices.length)*Math.PI*2-Math.PI/2;
    const r=Math.min(tc.width,tc.height)*0.35;
    const x=cx+Math.cos(angle)*r;
    const y=cy+Math.sin(angle)*r;
    // line to gateway
    tctx.strokeStyle='#333';tctx.lineWidth=1;tctx.beginPath();tctx.moveTo(cx,cy);tctx.lineTo(x,y);tctx.stroke();
    // node
    const col=d.type==='Unknown'?'#ff0044':d.type==='Drone'||d.type==='UGV'||d.type==='USV'?'#00ff88':'#00ccff';
    tctx.fillStyle=col;tctx.beginPath();tctx.arc(x,y,8,0,Math.PI*2);tctx.fill();
    tctx.fillStyle='#aaa';tctx.fillText(d.ip.split('.').pop(),x-8,y+20);
    tctx.fillText(d.type,x-12,y-12);
  });
}
drawTopo();
window.addEventListener('resize',drawTopo);
</script>
</body></html>
CYBERHTML
echo "  ✅ cyber.html created"
fi
else
echo ""
echo "[2/4] All templates present — skipping creation"
fi

# ── Step 3: Add Flask routes to c2_server.py ──
echo ""
echo "[3/4] Adding Flask routes to c2_server.py..."

if grep -q "'/ew'" "$C2_SERVER" 2>/dev/null; then
  echo "  [skip] Routes already exist in c2_server.py"
else
  # Find the right place to inject — after the last @app.route
  # We'll append before the main block or at the end of route definitions

  # Create a patch file with the new routes
  cat > /tmp/ew_routes_patch.py << 'ROUTEPATCH'

# ══════════════════════════════════════════════════════════
#  EW / SIGINT / CYBER ROUTES (Phase 9)
# ══════════════════════════════════════════════════════════

@app.route('/ew')
def ew_dashboard():
    """EW/SIGINT spectrum analyzer and emitter tracking."""
    return render_template('ew.html')

@app.route('/sigint')
def sigint_database():
    """SIGINT database — signal classification and analysis."""
    return render_template('sigint.html')

@app.route('/cyber')
def cyber_ops():
    """Cyber operations — WiFi, devices, vulnerabilities, IDS."""
    return render_template('cyber.html')

ROUTEPATCH

  # Find the line with "if __name__" or "def main" and inject before it
  if grep -q "if __name__" "$C2_SERVER"; then
    # Insert the routes before "if __name__"
    LINE_NUM=$(grep -n "if __name__" "$C2_SERVER" | head -1 | cut -d: -f1)
    head -n $((LINE_NUM - 1)) "$C2_SERVER" > /tmp/c2_patched.py
    cat /tmp/ew_routes_patch.py >> /tmp/c2_patched.py
    tail -n +$LINE_NUM "$C2_SERVER" >> /tmp/c2_patched.py
    cp /tmp/c2_patched.py "$C2_SERVER"
    echo "  ✅ Routes injected before __main__ block"
  elif grep -q "def main" "$C2_SERVER"; then
    LINE_NUM=$(grep -n "def main" "$C2_SERVER" | head -1 | cut -d: -f1)
    head -n $((LINE_NUM - 1)) "$C2_SERVER" > /tmp/c2_patched.py
    cat /tmp/ew_routes_patch.py >> /tmp/c2_patched.py
    tail -n +$LINE_NUM "$C2_SERVER" >> /tmp/c2_patched.py
    cp /tmp/c2_patched.py "$C2_SERVER"
    echo "  ✅ Routes injected before main()"
  else
    # Just append to end of file
    cat /tmp/ew_routes_patch.py >> "$C2_SERVER"
    echo "  ✅ Routes appended to end of c2_server.py"
  fi

  # Make sure render_template is imported
  if ! grep -q "render_template" "$C2_SERVER"; then
    sed -i 's/from flask import /from flask import render_template, /' "$C2_SERVER"
    echo "  ✅ Added render_template import"
  fi

  rm -f /tmp/ew_routes_patch.py /tmp/c2_patched.py
fi

# ── Step 4: Restart ──
echo ""
echo "[4/4] Restarting C2 server..."

# Kill existing c2_server if running
pkill -f "c2_server" 2>/dev/null && echo "  Stopped old C2 server" || echo "  No running C2 server found"
sleep 2

echo ""
echo "============================================"
echo "  ✅ FIX COMPLETE"
echo "============================================"
echo ""
echo "  Now restart MOS:"
echo "    cd ~/mos_ws && ./launch_mos.sh"
echo ""
echo "  Then open:"
echo "    http://localhost:5000/ew      ⚡ EW Dashboard"
echo "    http://localhost:5000/sigint   📡 SIGINT Database"
echo "    http://localhost:5000/cyber    🔓 Cyber Operations"
echo ""
echo "  Every page has a nav bar linking to all views."
echo "============================================"
