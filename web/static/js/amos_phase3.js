/* ================================================================
   MOS Phase 3 — UI Enhancement System
   Drops A (Polish) + B (Rich Panels) + C (New Capabilities)
   ================================================================ */
window.AMOS = window.AMOS || {};

/* ======================== TOAST ======================== */
AMOS.Toast={
  container:null,
  init(){
    this.container=document.getElementById('amos-toast-container');
    if(!this.container){
      this.container=document.createElement('div');
      this.container.id='amos-toast-container';
      this.container.className='amos-toast-container';
      document.body.appendChild(this.container);
    }
  },
  show(msg,type='info',dur=5000){
    if(!this.container)this.init();
    const t=document.createElement('div');
    t.className='amos-toast '+type;
    const ic={info:'ℹ️',warning:'⚠️',critical:'🔴',success:'✅'};
    t.innerHTML=(ic[type]||'')+'  '+msg;
    t.onclick=()=>t.remove();
    this.container.appendChild(t);
    if(dur>0)setTimeout(()=>{if(t.parentNode){t.style.opacity='0';t.style.transform='translateX(120%)';t.style.transition='all .3s';setTimeout(()=>t.remove(),300);}},dur);
  }
};

/* ======================== MODAL ======================== */
AMOS.Modal={
  overlay:null,
  init(){
    this.overlay=document.getElementById('amos-modal-overlay');
    if(!this.overlay){
      this.overlay=document.createElement('div');
      this.overlay.id='amos-modal-overlay';
      this.overlay.className='amos-modal-overlay';
      document.body.appendChild(this.overlay);
    }
    this.overlay.addEventListener('click',e=>{if(e.target===this.overlay)this.hide();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')this.hide();});
  },
  show(title,bodyHtml,actions){
    if(!this.overlay)this.init();
    actions=actions||[];
    let ah=actions.map(a=>`<button class="btn btn-sm ${a.cls||'btn-outline-light'}" onclick="${a.onclick}">${a.icon||''} ${a.label}</button>`).join('');
    this.overlay.innerHTML=`<div class="amos-modal">
      <div class="amos-modal-header"><h2>${title}</h2><button class="amos-modal-close" onclick="AMOS.Modal.hide()">&times;</button></div>
      <div class="amos-modal-body">${bodyHtml}</div>
      ${ah?'<div class="amos-modal-actions">'+ah+'</div>':''}
    </div>`;
    this.overlay.classList.add('active');
  },
  hide(){if(this.overlay)this.overlay.classList.remove('active');},

  showAsset(id){
    fetch('/api/phase3/asset/'+encodeURIComponent(id)).then(r=>r.json()).then(a=>{
      if(a.error){AMOS.Toast.show('Asset not found: '+id,'warning');return;}
      const hc=a.health>70?'green':a.health>30?'yellow':'red';
      const bc=(a.battery||100)>50?'#00ff41':(a.battery||100)>20?'#ffd700':'#ff0040';
      const tiers=['Manual','Assisted','Partial Auto','Conditional Auto','High Auto','Full Auto'];
      let body=`<div class="detail-grid">
        <div class="detail-item"><span class="detail-label">Callsign</span><span class="detail-value green">${a.callsign||a.name||a.id}</span></div>
        <div class="detail-item"><span class="detail-label">Type</span><span class="detail-value">${(a.type||'').toUpperCase()}</span></div>
        <div class="detail-item"><span class="detail-label">Position</span><span class="detail-value">${(a.lat||0).toFixed(4)}, ${(a.lng||0).toFixed(4)}</span></div>
        <div class="detail-item"><span class="detail-label">Altitude</span><span class="detail-value">${a.alt||0} ft</span></div>
        <div class="detail-item"><span class="detail-label">Speed</span><span class="detail-value">${a.speed||0} kts</span></div>
        <div class="detail-item"><span class="detail-label">Heading</span><span class="detail-value">${a.heading||0}&deg;</span></div>
        <div class="detail-item"><span class="detail-label">Status</span><span class="detail-value ${a.status==='active'?'green':'yellow'}">${(a.status||'unknown').toUpperCase()}</span></div>
        <div class="detail-item"><span class="detail-label">Autonomy</span><span class="detail-value">${tiers[a.autonomy||0]} (T${a.autonomy||0})</span></div>
      </div>
      <hr style="border-color:#1a1a3e;margin:14px 0">
      <div class="bar-label"><span>Health</span><span class="${hc}">${a.health||100}%</span></div>
      <div class="bar-gauge"><div class="bar-gauge-fill" style="width:${a.health||100}%;background:${a.health>70?'#00ff41':a.health>30?'#ffd700':'#ff0040'}"></div></div>
      <div class="bar-label"><span>Battery / Fuel</span><span>${a.battery||100}%</span></div>
      <div class="bar-gauge"><div class="bar-gauge-fill" style="width:${a.battery||100}%;background:${bc}"></div></div>`;
      if(a.sensors&&a.sensors.length)body+=`<hr style="border-color:#1a1a3e;margin:14px 0"><div class="detail-label">SENSORS</div><div style="color:#c0c0c0;font-family:monospace;font-size:12px;margin-top:4px">${a.sensors.map(s=>'<span style="margin-right:12px">▸ '+s+'</span>').join('')}</div>`;
      if(a.weapons&&a.weapons.length)body+=`<div class="detail-label" style="margin-top:10px">WEAPONS</div><div style="color:#c0c0c0;font-family:monospace;font-size:12px;margin-top:4px">${a.weapons.map(w=>'<span style="margin-right:12px">▸ '+w+'</span>').join('')}</div>`;
      AMOS.Modal.show('📡 '+( a.name||a.callsign||a.id),body,[
        {label:'📍 Send To',cls:'btn-outline-success',onclick:"AMOS.Planner.sendTo('"+a.id+"')"},
        {label:'🔄 Orbit',cls:'btn-outline-info',onclick:"AMOS.taskAsset('"+a.id+"','orbit')"},
        {label:'🏠 RTB',cls:'btn-outline-warning',onclick:"AMOS.taskAsset('"+a.id+"','rtb')"},
        {label:'🤖 Autonomy',cls:'btn-outline-light',onclick:"AMOS.showAutonomyPicker('"+a.id+"',"+(a.autonomy||0)+")"}
      ]);
    }).catch(e=>AMOS.Toast.show('Load failed: '+e,'critical'));
  },

  showThreat(id){
    fetch('/api/phase3/threat/'+encodeURIComponent(id)).then(r=>r.json()).then(t=>{
      if(t.error){AMOS.Toast.show('Threat not found: '+id,'warning');return;}
      const sc=t.threat_score>0.7?'red':t.threat_score>0.4?'yellow':'green';
      let body=`<div class="detail-grid">
        <div class="detail-item"><span class="detail-label">Classification</span><span class="detail-value red">${(t.type||'UNKNOWN').replace(/_/g,' ').toUpperCase()}</span></div>
        <div class="detail-item"><span class="detail-label">Threat Score</span><span class="detail-value ${sc}">${((t.threat_score||0)*100).toFixed(0)}%</span></div>
        <div class="detail-item"><span class="detail-label">Position</span><span class="detail-value">${(t.lat||0).toFixed(4)}, ${(t.lng||0).toFixed(4)}</span></div>
        <div class="detail-item"><span class="detail-label">Heading / Speed</span><span class="detail-value">${t.heading||0}&deg; / ${t.speed||0} kts</span></div>
        <div class="detail-item"><span class="detail-label">Nearest Friendly</span><span class="detail-value">${t.nearest_dist?t.nearest_dist.toFixed(1)+' km':'N/A'}</span></div>
        <div class="detail-item"><span class="detail-label">Status</span><span class="detail-value ${t.status==='neutralized'?'green':'red'}">${(t.status||'active').toUpperCase()}</span></div>
      </div>`;
      if(t.recommended_coa)body+=`<hr style="border-color:#1a1a3e;margin:14px 0"><div class="detail-label">RECOMMENDED COA</div><div style="color:#ffd700;font-family:monospace;font-size:13px;margin-top:5px">${t.recommended_coa}</div>`;
      AMOS.Modal.show('⚠️ THREAT: '+(t.type||t.id),body,[
        {label:'🎯 Track',cls:'btn-outline-info',onclick:"AMOS.engage('"+t.id+"','track')"},
        {label:'📡 Jam',cls:'btn-outline-warning',onclick:"AMOS.engage('"+t.id+"','jam')"},
        {label:'💥 Engage',cls:'btn-outline-danger',onclick:"AMOS.engage('"+t.id+"','engage')"},
        {label:'🛡️ Cyber Block',cls:'btn-outline-success',onclick:"AMOS.engage('"+t.id+"','cyber_block')"}
      ]);
    }).catch(e=>AMOS.Toast.show('Load failed: '+e,'critical'));
  }
};

/* ======================== SORTABLE TABLES ======================== */
AMOS.Tables={
  init(){
    document.querySelectorAll('table').forEach(tbl=>{
      if(!tbl.classList.contains('sortable'))tbl.classList.add('sortable');
      tbl.querySelectorAll('th').forEach((th,idx)=>{
        th.addEventListener('click',()=>{
          const asc=!th.classList.contains('sort-asc');
          tbl.querySelectorAll('th').forEach(h=>h.classList.remove('sort-asc','sort-desc'));
          th.classList.add(asc?'sort-asc':'sort-desc');
          this.sort(tbl,idx,asc);
        });
      });
    });
  },
  sort(tbl,col,asc){
    const tb=tbl.querySelector('tbody')||tbl;
    const rows=Array.from(tb.querySelectorAll('tr')).filter(r=>!r.querySelector('th'));
    rows.sort((a,b)=>{
      let av=(a.cells[col]?.textContent||'').trim(),bv=(b.cells[col]?.textContent||'').trim();
      let an=parseFloat(av.replace(/[^0-9.\-]/g,'')),bn=parseFloat(bv.replace(/[^0-9.\-]/g,''));
      if(!isNaN(an)&&!isNaN(bn))return asc?an-bn:bn-an;
      return asc?av.localeCompare(bv):bv.localeCompare(av);
    });
    rows.forEach(r=>tb.appendChild(r));
  }
};

/* ======================== MESH / COMM LINES ======================== */
AMOS.Mesh={
  lines:[],map:null,
  init(map){this.map=map;},
  update(assets){
    if(!this.map)return;
    this.lines.forEach(l=>this.map.removeLayer(l));this.lines=[];
    const list=Array.isArray(assets)?assets:Object.values(assets||{});
    const range={air:80,ground:30,maritime:50,awacs:150};
    for(let i=0;i<list.length;i++){
      for(let j=i+1;j<list.length;j++){
        const a=list[i],b=list[j];
        if(!a.lat||!b.lat)continue;
        const d=this._hav(a.lat,a.lng,b.lat,b.lng);
        const mr=Math.max(range[a.type]||30,range[b.type]||30);
        if(d<=mr){
          const q=1-(d/mr);
          const c=q>.6?'rgba(0,255,65,0.5)':q>.3?'rgba(255,215,0,0.35)':'rgba(255,0,64,0.3)';
          const ln=L.polyline([[a.lat,a.lng],[b.lat,b.lng]],{color:c,weight:q>.6?1.5:1,dashArray:q<.3?'5 5':null}).addTo(this.map);
          ln.bindTooltip(`${a.callsign||a.id} ↔ ${b.callsign||b.id}<br>${d.toFixed(1)}km — ${(q*100).toFixed(0)}%`,{className:'amos-mesh-tooltip'});
          this.lines.push(ln);
        }
      }
    }
  },
  _hav(a,b,c,d){const R=6371,dL=(c-a)*Math.PI/180,dG=(d-b)*Math.PI/180,x=Math.sin(dL/2)**2+Math.cos(a*Math.PI/180)*Math.cos(c*Math.PI/180)*Math.sin(dG/2)**2;return R*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));}
};

/* ======================== CONTEXT MENU ======================== */
AMOS.ContextMenu={
  menu:null,latlng:null,
  init(map){
    this.menu=document.createElement('div');this.menu.className='amos-ctx-menu';document.body.appendChild(this.menu);
    map.on('contextmenu',e=>{e.originalEvent.preventDefault();this.latlng=e.latlng;this._show(e.originalEvent.clientX,e.originalEvent.clientY);});
    document.addEventListener('click',()=>this.hide());
  },
  _show(x,y){
    this.menu.innerHTML=`
      <div class="amos-ctx-item" onclick="AMOS.ContextMenu.act('wp')"><span class="ctx-icon">📍</span>Add Waypoint</div>
      <div class="amos-ctx-item" onclick="AMOS.ContextMenu.act('send')"><span class="ctx-icon">➡️</span>Send Nearest Asset</div>
      <div class="amos-ctx-item" onclick="AMOS.ContextMenu.act('orbit')"><span class="ctx-icon">🔄</span>Orbit Pattern</div>
      <div class="amos-ctx-item" onclick="AMOS.ContextMenu.act('threat')"><span class="ctx-icon">⚠️</span>Mark Threat</div>
      <div class="amos-ctx-item" onclick="AMOS.ContextMenu.act('measure')"><span class="ctx-icon">📏</span>Measure Distance</div>`;
    this.menu.style.left=x+'px';this.menu.style.top=y+'px';this.menu.classList.add('active');
  },
  hide(){if(this.menu)this.menu.classList.remove('active');},
  act(type){
    const ll=this.latlng;if(!ll)return;this.hide();
    if(type==='wp'){AMOS.Planner.addWaypoint(ll.lat,ll.lng);}
    else if(type==='send'){
      fetch('/api/phase3/send_nearest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat:ll.lat,lng:ll.lng})}).then(r=>r.json()).then(d=>AMOS.Toast.show('Sending '+d.asset+' to '+ll.lat.toFixed(4)+', '+ll.lng.toFixed(4),'success'));
    }else if(type==='orbit'){
      fetch('/api/phase3/task_nearest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lat:ll.lat,lng:ll.lng,task:'orbit'})}).then(r=>r.json()).then(d=>AMOS.Toast.show(d.asset+' entering orbit','success'));
    }else if(type==='threat'){
      if(window.aamosMap)L.marker([ll.lat,ll.lng],{icon:L.divIcon({className:'',html:'<div style="color:red;font-size:22px">⚠️</div>'})}).addTo(window.aamosMap);
      AMOS.Toast.show('Threat marked at '+ll.lat.toFixed(4)+', '+ll.lng.toFixed(4),'warning');
    }else AMOS.Toast.show(type+' at '+ll.lat.toFixed(4)+', '+ll.lng.toFixed(4),'info');
  }
};

/* ======================== KILL CHAIN ======================== */
AMOS.KillChain={
  el:null,steps:['FIND','FIX','TRACK','TARGET','ENGAGE','ASSESS'],
  init(id){this.el=document.getElementById(id);},
  render(stage){
    if(!this.el)return;
    const si=this.steps.indexOf((stage||'').toUpperCase());
    this.el.innerHTML=this.steps.map((s,i)=>{
      let c=i<si?'complete':i===si?'active':'';
      let ac=i<=si?'active':'';
      return`<div class="kc-step ${c}">${s}</div>${i<this.steps.length-1?'<div class="kc-arrow '+ac+'">▶</div>':''}`;
    }).join('');
  },
  update(){fetch('/api/phase3/killchain').then(r=>r.json()).then(d=>{if(d.active_engagement)this.render(d.active_engagement.stage);}).catch(()=>{});}
};

/* ======================== ALERT POLLER ======================== */
AMOS.Alerts={
  lastId:0,interval:null,
  init(ms){this.poll();this.interval=setInterval(()=>this.poll(),ms||5000);},
  poll(){
    fetch('/api/phase3/alerts?since='+this.lastId).then(r=>r.json()).then(arr=>{
      if(!arr||!arr.length)return;
      arr.forEach(a=>{AMOS.Toast.show(a.message,a.severity||'info');if(a.id>this.lastId)this.lastId=a.id;});
    }).catch(()=>{});
  }
};

/* ======================== METRICS / CHARTS ======================== */
AMOS.Metrics={
  charts:{},
  init(){if(typeof Chart==='undefined')return;this.fetch();setInterval(()=>this.fetch(),10000);},
  fetch(){fetch('/api/phase3/metrics').then(r=>r.json()).then(d=>this.render(d)).catch(()=>{});},
  render(d){
    this._chart('chart-threats','doughnut',{labels:['Neutralized','Active','Tracking'],datasets:[{data:[d.threats_neutralized||0,d.threats_active||0,d.threats_tracking||0],backgroundColor:['#00ff41','#ff0040','#ffd700']}]});
    this._chart('chart-health','bar',{labels:d.asset_labels||[],datasets:[{label:'Health %',data:d.asset_health||[],backgroundColor:(d.asset_health||[]).map(h=>h>70?'#00ff41':h>30?'#ffd700':'#ff0040')}]});
    this._chart('chart-battery','bar',{labels:d.asset_labels||[],datasets:[{label:'Battery %',data:d.asset_battery||[],backgroundColor:'#00bfff'}]});
    this._chart('chart-events','line',{labels:d.event_times||[],datasets:[{label:'Events',data:d.event_counts||[],borderColor:'#00ff41',backgroundColor:'rgba(0,255,65,.1)',fill:true,tension:.3}]});
  },
  _chart(id,type,data){
    const cv=document.getElementById(id);if(!cv)return;
    if(this.charts[id]){this.charts[id].data=data;this.charts[id].update();return;}
    const opts={responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#888',font:{family:'monospace',size:10}}}}};
    if(type!=='doughnut')opts.scales={x:{ticks:{color:'#555',font:{family:'monospace',size:9}},grid:{color:'#1a1a3e'}},y:{ticks:{color:'#555',font:{family:'monospace',size:9}},grid:{color:'#1a1a3e'},beginAtZero:true}};
    this.charts[id]=new Chart(cv.getContext('2d'),{type,data,options:opts});
  }
};

/* ======================== EW SPECTRUM ======================== */
AMOS.EW={
  canvas:null,ctx:null,emitters:[],jams:[],af:null,
  init(id){
    this.canvas=document.getElementById(id);if(!this.canvas)return;
    this.ctx=this.canvas.getContext('2d');this._resize();
    window.addEventListener('resize',()=>this._resize());
    this._fetchLoop();this._draw();
  },
  _resize(){if(!this.canvas)return;this.canvas.width=this.canvas.offsetWidth||600;this.canvas.height=this.canvas.offsetHeight||250;},
  _fetchLoop(){this._fetchData();setInterval(()=>this._fetchData(),3000);},
  _fetchData(){fetch('/api/phase3/ew/spectrum').then(r=>r.json()).then(d=>{this.emitters=d.emitters||[];this.jams=d.jamming||[];}).catch(()=>{});},
  _draw(){
    const loop=()=>{this._render();this.af=requestAnimationFrame(loop);};loop();
  },
  _render(){
    if(!this.ctx)return;const c=this.ctx,w=this.canvas.width,h=this.canvas.height;
    c.fillStyle='#050510';c.fillRect(0,0,w,h);
    c.strokeStyle='#0a1a0a';c.lineWidth=.5;
    for(let i=1;i<10;i++){c.beginPath();c.moveTo(0,h*i/10);c.lineTo(w,h*i/10);c.stroke();c.beginPath();c.moveTo(w*i/10,0);c.lineTo(w*i/10,h);c.stroke();}
    this.jams.forEach(j=>{const x1=(j.start_mhz/6000)*w,x2=(j.end_mhz/6000)*w;c.fillStyle='rgba(255,0,64,.15)';c.fillRect(x1,0,x2-x1,h);c.fillStyle='#ff0040';c.font='9px monospace';c.fillText('JAM',x1+3,14);});
    c.beginPath();c.strokeStyle='#00ff41';c.lineWidth=1.2;
    for(let x=0;x<w;x++){
      let y=h*.82+(Math.random()-.5)*h*.04;
      this.emitters.forEach(em=>{const ex=(em.freq_mhz/6000)*w,d=Math.abs(x-ex),bw=(em.bandwidth||20)/6000*w;if(d<bw*3){const s=((em.power_dbm||(-30))+120)/120*h*.6;y-=s*Math.exp(-d*d/(2*bw*bw));}});
      x===0?c.moveTo(x,y):c.lineTo(x,y);
    }
    c.stroke();
    c.fillStyle='#00ffff';c.font='9px monospace';
    this.emitters.forEach(em=>{const ex=(em.freq_mhz/6000)*w;c.fillText(em.freq_mhz+'MHz',ex-18,28);if(em.type)c.fillText(em.type,ex-18,38);});
    c.fillStyle='#00ff4180';c.font='10px monospace';c.fillText('0 MHz',5,h-6);c.fillText('6 GHz',w-48,h-6);
  }
};

/* ======================== SIGINT WATERFALL ======================== */
AMOS.SIGINT={
  canvas:null,ctx:null,af:null,
  init(id){
    this.canvas=document.getElementById(id);if(!this.canvas)return;
    this.ctx=this.canvas.getContext('2d');this._resize();
    window.addEventListener('resize',()=>this._resize());
    let last=0;const loop=t=>{if(t-last>80){this._addLine();last=t;}this.af=requestAnimationFrame(loop);};loop(0);
  },
  _resize(){if(!this.canvas)return;this.canvas.width=this.canvas.offsetWidth||600;this.canvas.height=this.canvas.offsetHeight||300;},
  _addLine(){
    if(!this.ctx)return;const c=this.ctx,w=this.canvas.width,h=this.canvas.height;
    const img=c.getImageData(0,0,w,h-1);c.putImageData(img,0,1);
    const row=c.createImageData(w,1);
    const sigs=[80,160,300,420,520];
    for(let x=0;x<w;x++){
      let v=Math.random()*.08;
      sigs.forEach(s=>{const d=Math.abs(x-s*(w/600));if(d<6)v+=(.4+Math.random()*.6)*Math.exp(-d*d/12);});
      v=Math.min(v,1);const[r,g,b]=this._heat(v);
      row.data[x*4]=r;row.data[x*4+1]=g;row.data[x*4+2]=b;row.data[x*4+3]=255;
    }
    c.putImageData(row,0,0);
  },
  _heat(v){
    if(v<.25)return[0,0,Math.floor(v*4*160)];
    if(v<.5)return[0,Math.floor((v-.25)*4*255),150];
    if(v<.75)return[Math.floor((v-.5)*4*255),255,Math.floor(150-(v-.5)*4*150)];
    return[255,Math.floor(255-(v-.75)*4*200),0];
  }
};

/* ======================== CYBER TOPOLOGY ======================== */
AMOS.Cyber={
  el:null,
  init(id){this.el=document.getElementById(id);if(!this.el)return;this._fetch();setInterval(()=>this._fetch(),6000);},
  _fetch(){fetch('/api/phase3/cyber/topology').then(r=>r.json()).then(d=>this._render(d.nodes||[],d.links||[])).catch(()=>{});},
  _render(nodes,links){
    if(!this.el)return;
    const w=this.el.offsetWidth||600,h=350,cx=w/2,cy=h/2;
    const pos=nodes.map((n,i)=>{const a=(i/nodes.length)*Math.PI*2,r=Math.min(w,h)*.35;return{...n,x:cx+Math.cos(a)*r,y:cy+Math.sin(a)*r};});
    const pm={};pos.forEach(n=>pm[n.id]=n);
    let svg=`<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">`;
    links.forEach(l=>{const f=pm[l.from],t=pm[l.to];if(!f||!t)return;const c=l.attack?'attack':l.active?'active':'';svg+=`<line class="topo-link ${c}" x1="${f.x}" y1="${f.y}" x2="${t.x}" y2="${t.y}"/>`;});
    pos.forEach(n=>{const cl=n.compromised?'#ff0040':n.status==='secure'?'#00ff41':'#ffd700';svg+=`<g class="topo-node" onclick="AMOS.Toast.show('${n.name}: ${n.status}','info')"><circle cx="${n.x}" cy="${n.y}" r="14" fill="${cl}" opacity=".75"/><circle cx="${n.x}" cy="${n.y}" r="14" fill="none" stroke="${cl}" stroke-width="2"/><text x="${n.x}" y="${n.y+26}" text-anchor="middle">${n.name}</text></g>`;});
    svg+='</svg>';this.el.innerHTML=svg;
  }
};

/* ======================== MISSION PLANNER ======================== */
AMOS.Planner={
  map:null,drawing:false,wps:[],markers:[],line:null,asset:null,
  init(map){this.map=map;},
  startDrawing(assetId){
    this.drawing=true;this.asset=assetId;this.wps=[];this.clearDrawing();
    AMOS.Toast.show('Click map to add waypoints. Double-click to finish.','info',8000);
    this._onClick=e=>{if(this.drawing)this.addWaypoint(e.latlng.lat,e.latlng.lng);};
    this._onDbl=e=>{if(this.drawing)this.stopDrawing();};
    this.map.on('click',this._onClick);this.map.on('dblclick',this._onDbl);
    this.map.getContainer().style.cursor='crosshair';
  },
  addWaypoint(lat,lng){
    this.wps.push({lat,lng});const n=this.wps.length;
    const m=L.marker([lat,lng],{icon:L.divIcon({className:'',html:`<div style="background:#00ff41;color:#000;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;font-family:monospace;border:2px solid #fff">${n}</div>`})}).addTo(this.map);
    this.markers.push(m);
    if(this.line)this.map.removeLayer(this.line);
    if(this.wps.length>1)this.line=L.polyline(this.wps.map(w=>[w.lat,w.lng]),{color:'#00ff41',weight:2,dashArray:'8 4'}).addTo(this.map);
    AMOS.Toast.show('WP '+n+': '+lat.toFixed(4)+', '+lng.toFixed(4),'success',2000);
  },
  stopDrawing(){
    this.drawing=false;
    if(this.map){this.map.off('click',this._onClick);this.map.off('dblclick',this._onDbl);this.map.getContainer().style.cursor='';}
    if(this.wps.length)this.saveRoute();
  },
  saveRoute(){
    fetch('/api/phase3/mission/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_id:this.asset,waypoints:this.wps})}).then(r=>r.json()).then(d=>AMOS.Toast.show('Mission saved: '+(d.mission_id||'OK'),'success')).catch(e=>AMOS.Toast.show('Save failed','critical'));
  },
  clearDrawing(){this.markers.forEach(m=>this.map.removeLayer(m));this.markers=[];if(this.line){this.map.removeLayer(this.line);this.line=null;}this.wps=[];},
  sendTo(id){AMOS.Modal.hide();this.startDrawing(id);}
};

/* ======================== TWIN GAUGES ======================== */
AMOS.Twin={
  el:null,
  init(id){this.el=document.getElementById(id);if(!this.el)this.el=document.querySelector('.twin-gauges');this._fetch();setInterval(()=>this._fetch(),5000);},
  _fetch(){
    fetch('/api/phase3/metrics').then(r=>r.json()).then(d=>{
      if(!this.el)return;const assets=d.assets_detail||[];
      this.el.innerHTML=assets.map(a=>{
        const hc=(a.health||100)>70?'#00ff41':(a.health||100)>30?'#ffd700':'#ff0040';
        const bc=(a.battery||100)>50?'#00bfff':(a.battery||100)>20?'#ffd700':'#ff0040';
        return`<div class="gauge-card" onclick="AMOS.Modal.showAsset('${a.id}')">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div><div style="color:${a.status==='active'?'#00ff41':'#ffd700'};font-family:monospace;font-weight:bold;font-size:13px">${a.callsign||a.id}</div><div style="color:#555;font-family:monospace;font-size:10px">${(a.type||'').toUpperCase()}</div></div>
            <div class="gauge-circle" style="--pct:${a.health||100};--gauge-color:${hc};width:55px;height:55px"><div class="gauge-inner" style="width:40px;height:40px;font-size:11px">${a.health||100}%</div></div>
          </div>
          <div class="bar-label"><span>Battery</span><span>${a.battery||100}%</span></div>
          <div class="bar-gauge"><div class="bar-gauge-fill" style="width:${a.battery||100}%;background:${bc}"></div></div>
          <div style="display:flex;justify-content:space-between;margin-top:6px;font-family:monospace;font-size:10px;color:#555"><span>${(a.lat||0).toFixed(3)}, ${(a.lng||0).toFixed(3)}</span><span>T${a.autonomy||0}</span></div>
        </div>`;
      }).join('');
    }).catch(()=>{});
  }
};

/* ======================== AAR TIMELINE ======================== */
AMOS.AAR={
  el:null,
  init(id){this.el=document.getElementById(id);this._fetch();},
  _fetch(){fetch('/api/phase3/aar/timeline').then(r=>r.json()).then(ev=>this._render(ev)).catch(()=>{});},
  _render(events){
    if(!this.el||!events)return;
    this.el.innerHTML=`<div style="margin-bottom:12px;display:flex;gap:6px;flex-wrap:wrap">
      <button class="btn btn-sm btn-outline-light" onclick="AMOS.AAR.filter('all')">All</button>
      <button class="btn btn-sm btn-outline-danger" onclick="AMOS.AAR.filter('threat')">Threats</button>
      <button class="btn btn-sm btn-outline-warning" onclick="AMOS.AAR.filter('ew')">EW</button>
      <button class="btn btn-sm btn-outline-info" onclick="AMOS.AAR.filter('cyber')">Cyber</button>
      <button class="btn btn-sm btn-outline-success" onclick="AMOS.AAR.filter('movement')">Movement</button>
    </div><div class="amos-timeline" id="aar-tl-inner">${events.map(e=>`<div class="tl-event ${e.type||''}" data-type="${e.type||''}"><div class="tl-time">${e.time||''}</div><div class="tl-title">${e.title||''}</div><div class="tl-desc">${e.description||''}</div></div>`).join('')}</div>`;
  },
  filter(t){document.querySelectorAll('#aar-tl-inner .tl-event').forEach(el=>{el.style.display=(t==='all'||el.dataset.type===t)?'':'none';});}
};

/* ======================== HELPERS ======================== */
AMOS.taskAsset=function(id,task){
  AMOS.Modal.hide();
  fetch('/api/phase3/asset/'+id+'/task',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task})}).then(r=>r.json()).then(()=>AMOS.Toast.show(id+': '+task.toUpperCase()+' confirmed','success')).catch(e=>AMOS.Toast.show('Failed: '+e,'critical'));
};
AMOS.engage=function(tid,action){
  AMOS.Modal.hide();
  fetch('/api/phase3/engage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({threat_id:tid,action})}).then(r=>r.json()).then(d=>AMOS.Toast.show(action.toUpperCase()+' on '+tid+': '+(d.status||'initiated'),d.status==='approved'?'success':'warning')).catch(e=>AMOS.Toast.show('Failed: '+e,'critical'));
};
AMOS.showAutonomyPicker=function(id,cur){
  const tiers=['T0: Manual','T1: Assisted','T2: Partial Auto','T3: Conditional','T4: High Auto','T5: Full Auto'];
  const b=tiers.map((t,i)=>`<div style="padding:8px 12px;cursor:pointer;border:1px solid ${i===cur?'#00ff41':'#1a1a3e'};border-radius:4px;margin:4px 0;font-family:monospace;color:${i===cur?'#00ff41':'#c0c0c0'}" onclick="AMOS.setAutonomy('${id}',${i})">${t}${i===cur?' ✓':''}</div>`).join('');
  AMOS.Modal.show('🤖 Set Autonomy: '+id,b);
};
AMOS.setAutonomy=function(id,tier){
  fetch('/api/phase3/asset/'+id+'/task',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:'set_autonomy',autonomy:tier})}).then(()=>{AMOS.Modal.hide();AMOS.Toast.show(id+' autonomy → T'+tier,'success');});
};

/* ======================== FIND LEAFLET MAP ======================== */
AMOS._findMap=function(){
  if(window.aamosMap)return window.aamosMap;
  if(window.map&&window.map._leaflet_id)return window.map;
  for(const k of Object.getOwnPropertyNames(window)){try{const v=window[k];if(v&&v._leaflet_id&&v.getCenter)return v;}catch(e){}}
  return null;
};

/* ======================== AUTO-INIT ======================== */
document.addEventListener('DOMContentLoaded',()=>{
  AMOS.Toast.init();
  AMOS.Modal.init();
  AMOS.Tables.init();

  const path=window.location.pathname;
  const main=document.querySelector('.container-fluid')||document.querySelector('.container')||document.querySelector('main')||document.body;
  function ensure(id,html){if(!document.getElementById(id))main.insertAdjacentHTML('beforeend',html);}

  /* Dashboard / main */
  if(path==='/'||path.includes('dashboard')){
    ensure('kill-chain','<div class="kill-chain" id="kill-chain" style="margin:15px 0"></div>');
    ensure('chart-threats',`<div class="metrics-grid">
      <div class="metric-card"><h4>Threat Status</h4><canvas id="chart-threats"></canvas></div>
      <div class="metric-card"><h4>Asset Health</h4><canvas id="chart-health"></canvas></div>
      <div class="metric-card"><h4>Battery / Fuel</h4><canvas id="chart-battery"></canvas></div>
      <div class="metric-card"><h4>Event Timeline</h4><canvas id="chart-events"></canvas></div>
    </div>`);
    const poll=setInterval(()=>{
      const m=AMOS._findMap();
      if(m){clearInterval(poll);window.aamosMap=m;AMOS.Mesh.init(m);AMOS.ContextMenu.init(m);AMOS.Planner.init(m);
        function meshRefresh(){fetch('/api/phase3/metrics').then(r=>r.json()).then(d=>AMOS.Mesh.update(d.assets_detail||[])).catch(()=>{});}
        meshRefresh();setInterval(meshRefresh,5000);
      }
    },500);
    setTimeout(()=>{AMOS.KillChain.init('kill-chain');AMOS.KillChain.update();setInterval(()=>AMOS.KillChain.update(),10000);},600);
    AMOS.Metrics.init();
  }

  /* EW */
  if(path.includes('ew')){
    ensure('ew-spectrum','<h4 style="color:#00ff41;font-family:monospace;margin:15px 0 5px">📡 RF SPECTRUM ANALYZER</h4><div class="spectrum-container"><canvas id="ew-spectrum"></canvas></div>');
    setTimeout(()=>AMOS.EW.init('ew-spectrum'),200);
  }
  /* SIGINT */
  if(path.includes('sigint')){
    ensure('sigint-waterfall','<h4 style="color:#00ffff;font-family:monospace;margin:15px 0 5px">📻 SIGNAL WATERFALL</h4><div class="waterfall-container"><canvas id="sigint-waterfall"></canvas></div>');
    setTimeout(()=>AMOS.SIGINT.init('sigint-waterfall'),200);
  }
  /* Cyber */
  if(path.includes('cyber')){
    ensure('cyber-topology','<h4 style="color:#00bfff;font-family:monospace;margin:15px 0 5px">🔒 NETWORK TOPOLOGY</h4><div class="topo-container" id="cyber-topology"></div>');
    setTimeout(()=>AMOS.Cyber.init('cyber-topology'),200);
  }
  /* TWIN */
  if(path.includes('twin')||path.includes('digital')){
    ensure('twin-gauges','<h4 style="color:#00ff41;font-family:monospace;margin:15px 0 5px">🤖 ASSET HEALTH MATRIX</h4><div class="gauge-row" id="twin-gauges"></div>');
    setTimeout(()=>AMOS.Twin.init('twin-gauges'),200);
  }
  /* AAR */
  if(path.includes('aar')){
    ensure('aar-timeline','<div id="aar-timeline" style="margin:15px 0"></div>');
    setTimeout(()=>AMOS.AAR.init('aar-timeline'),200);
  }

  /* Alerts on every page */
  AMOS.Alerts.init(5000);

  /* Auto-bind clickable table rows */
  setTimeout(()=>{
    document.querySelectorAll('table tbody tr').forEach(row=>{
      const fc=(row.cells[0]?.textContent||'').trim();
      if(/^(air|ground|gnd|maritime|mar|awacs|uav|ugv|usv|reaper|predator|ghost|shadow)/i.test(fc)){
        row.style.cursor='pointer';row.title='Click for asset details';
        row.addEventListener('click',()=>AMOS.Modal.showAsset(fc));
      }else if(/^(threat|hostile|bogey|tgt)/i.test(fc)||row.classList.contains('threat-row')){
        row.style.cursor='pointer';row.title='Click for threat details';
        row.addEventListener('click',()=>AMOS.Modal.showThreat(fc));
      }
    });
  },1000);

  console.log('%c[AMOS] Phase 3 UI loaded ✓','color:#00ff41;font-weight:bold;font-size:14px');
});
