/* ═══════════════════════════════════════════════════════════
   AMOS Phase 3 — Autonomous Mission Operating System
   Complete UI: Modals, Sorting, Mesh, Toasts, Swarm Patterns
   ═══════════════════════════════════════════════════════════ */
console.log('[AMOS] Phase 3 JS loading...');

(function(){
"use strict";

/* ── NAMESPACE ── */
var A = window.AMOS = window.AMOS || {};

/* ═══════════════════════════
   TOAST NOTIFICATIONS
   ═══════════════════════════ */
A.toast = function(msg, sev){
    sev = sev || 'info';
    var c = document.getElementById('amos-toast-container');
    if(!c) return;
    var colors = {info:'#00ff41',success:'#00ff41',warning:'#ffd700',critical:'#ff0040',error:'#ff0040'};
    var col = colors[sev] || colors.info;
    var t = document.createElement('div');
    t.className = 'amos-toast';
    t.style.border = '1px solid ' + col;
    t.style.color = col;
    t.style.boxShadow = '0 0 15px ' + col + '33';
    t.textContent = '\u2B21 ' + msg;
    c.appendChild(t);
    setTimeout(function(){t.style.opacity='0';t.style.transition='opacity .5s'},4000);
    setTimeout(function(){if(t.parentNode)t.parentNode.removeChild(t)},4500);
};

/* ═══════════════════════════
   MODAL SYSTEM
   ═══════════════════════════ */
A.modal = {};

A.modal.open = function(title, bodyHtml, actionsHtml){
    var ov = document.getElementById('amos-modal-overlay');
    if(!ov) return;
    document.getElementById('amos-modal-title').textContent = title;
    document.getElementById('amos-modal-body').innerHTML = bodyHtml;
    document.getElementById('amos-modal-actions').innerHTML = actionsHtml || '';
    ov.style.display = 'block';
};

A.modal.close = function(){
    var ov = document.getElementById('amos-modal-overlay');
    if(ov) ov.style.display = 'none';
};

A.modal.showAsset = function(id){
    A.modal.open('\uD83D\uDCE1 ASSET: ' + id, '<div style="color:#666">Loading...</div>', '');
    fetch('/api/phase3/asset/' + encodeURIComponent(id))
    .then(function(r){return r.json()})
    .then(function(d){
        if(d.error){
            A.modal.open('\u26A0 ASSET: ' + id,
                '<div style="color:#ff4444">Not found: '+id+'</div>' +
                (d.available ? '<div style="color:#555;margin-top:8px;font-size:11px">Available keys: '+d.available.join(', ')+'</div>' : ''), '');
            return;
        }
        var h = '<table>';
        var skip = ['description','recommended_coa','sensors','weapons','waypoints'];
        for(var k in d){
            if(skip.indexOf(k) >= 0) continue;
            var v = d[k]; if(typeof v === 'object') v = JSON.stringify(v);
            var c = '#ccc';
            if(k==='health'||k==='battery'){var n=parseFloat(v);c=n>70?'#00ff41':n>40?'#ffd700':'#ff0040'}
            if(k==='status') c = v==='active'||v==='operational'?'#00ff41':v==='rtb'?'#ffd700':'#ff8800';
            h += '<tr><td>'+k+'</td><td style="color:'+c+'">'+v+'</td></tr>';
        }
        h += '</table>';
        if(d.sensors && d.sensors.length) h += '<div style="margin-top:8px;color:#666;font-size:11px">Sensors: '+d.sensors.join(', ')+'</div>';
        var btns = '<button class="amos-btn amos-btn-green" onclick="AMOS.taskAsset(\''+id+'\',\'orbit\')">\u27F3 Orbit</button>' +
                   '<button class="amos-btn amos-btn-yellow" onclick="AMOS.taskAsset(\''+id+'\',\'rtb\')">\u23CE RTB</button>' +
                   '<button class="amos-btn amos-btn-blue" onclick="AMOS.taskAsset(\''+id+'\',\'hold\')">\u23F8 Hold</button>';
        A.modal.open('\uD83D\uDCE1 ' + (d.callsign||d.name||id), h, btns);
    }).catch(function(e){ A.modal.open('Error', '<div style="color:red">'+e.message+'</div>','')});
};

A.modal.showThreat = function(id){
    A.modal.open('\u26A0 THREAT: ' + id, '<div style="color:#666">Loading...</div>', '');
    fetch('/api/phase3/threat/' + encodeURIComponent(id))
    .then(function(r){return r.json()})
    .then(function(d){
        if(d.error){
            A.modal.open('\u26A0 THREAT: ' + id, '<div style="color:#ff4444">Not found</div>','');
            return;
        }
        var h = '<table>';
        for(var k in d){
            if(k==='recommended_coa') continue;
            var v = d[k]; if(typeof v==='object') v=JSON.stringify(v);
            var c = '#ccc';
            if(k==='threat_score'){var n=parseFloat(v);c=n>0.7?'#ff0040':n>0.4?'#ffd700':'#00ff41'}
            if(k==='status') c=v==='active'?'#ff0040':'#ffd700';
            h += '<tr><td>'+k+'</td><td style="color:'+c+'">'+v+'</td></tr>';
        }
        h += '</table>';
        if(d.recommended_coa){
            h += '<div style="margin-top:12px;padding:10px;background:#1a1a0a;border:1px solid #ffd700;border-radius:6px">' +
                 '<div style="color:#ffd700;font-size:10px;margin-bottom:4px">RECOMMENDED COA</div>' +
                 '<div style="color:#eee;font-size:12px">'+d.recommended_coa+'</div></div>';
        }
        var btns = '<button class="amos-btn amos-btn-green" onclick="AMOS.engageThreat(\''+id+'\',\'track\')">\uD83D\uDC41 Track</button>' +
                   '<button class="amos-btn amos-btn-yellow" onclick="AMOS.engageThreat(\''+id+'\',\'jam\')">\uD83D\uDCE1 Jam</button>' +
                   '<button class="amos-btn amos-btn-red" onclick="AMOS.engageThreat(\''+id+'\',\'engage\')">\uD83C\uDFAF Engage</button>';
        A.modal.open('\u26A0 THREAT: ' + (d.type||d.id||id), h, btns);
    }).catch(function(e){A.modal.open('Error','<div style="color:red">'+e.message+'</div>','')});
};

/* Commands */
A.taskAsset = function(id, task){
    fetch('/api/phase3/asset/'+encodeURIComponent(id)+'/task',{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:task})
    }).then(function(r){return r.json()}).then(function(d){
        A.toast(id+' \u2192 '+task.toUpperCase(), task==='rtb'?'warning':'success');
    });
};

A.engageThreat = function(id, action){
    fetch('/api/phase3/engage',{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({threat_id:id,action:action})
    }).then(function(r){return r.json()}).then(function(d){
        A.toast(action.toUpperCase()+' on '+id, action==='engage'?'critical':'warning');
    });
};


/* ═══════════════════════════
   TABLE SORTING
   ═══════════════════════════ */
A.initSorting = function(){
    document.querySelectorAll('table thead th').forEach(function(th, colIdx){
        if(th.dataset.sortBound) return;
        th.dataset.sortBound = '1';
        th.addEventListener('click', function(){
            var table = th.closest('table');
            var tbody = table.querySelector('tbody');
            if(!tbody) return;
            var rows = Array.from(tbody.querySelectorAll('tr'));
            var asc = th.dataset.sortDir !== 'asc';
            th.dataset.sortDir = asc ? 'asc' : 'desc';
            // Clear sort indicators
            table.querySelectorAll('th').forEach(function(h){h.textContent = h.textContent.replace(/ [\u25B2\u25BC]/g,'')});
            th.textContent += asc ? ' \u25B2' : ' \u25BC';
            rows.sort(function(a,b){
                var av = a.cells[colIdx] ? a.cells[colIdx].textContent.trim() : '';
                var bv = b.cells[colIdx] ? b.cells[colIdx].textContent.trim() : '';
                // Strip % signs for numeric comparison
                var an = parseFloat(av.replace('%','')), bn = parseFloat(bv.replace('%',''));
                if(!isNaN(an)&&!isNaN(bn)) return asc ? an-bn : bn-an;
                return asc ? av.localeCompare(bv) : bv.localeCompare(av);
            });
            rows.forEach(function(r){tbody.appendChild(r)});
            A.toast('Sorted by ' + th.textContent.replace(/ [\u25B2\u25BC]/g,''), 'info');
        });
    });
    console.log('[AMOS] Table sorting bound');
};


/* ═══════════════════════════
   ROW CLICK → MODAL
   ═══════════════════════════ */
A.bindRows = function(){
    document.querySelectorAll('table tbody tr').forEach(function(row){
        if(row.dataset.amosBound) return;
        row.dataset.amosBound = '1';
        var cells = Array.from(row.cells).map(function(c){return c.textContent.trim()});
        var txt = cells.join(' ').toLowerCase();

        var assetRe = /\b(air|ground|gnd|maritime|mar|awacs|uav|ugv|usv|reaper|ghost|shadow|wolf|shark|mule|viper|hawk|eagle|spectre|relay|predator)\b/i;
        var threatRe = /\b(threat|hostile|bogey|enemy|jammer|hostile-)/i;

        var isAsset = assetRe.test(txt) && !threatRe.test(txt);
        var isThreat = threatRe.test(txt);

        if(isAsset || isThreat){
            row.setAttribute('data-clickable','1');
            row.title = 'Click for details';
            row.addEventListener('click', function(){
                var id = (cells[0]||cells[1]||'').trim();
                if(isThreat) A.modal.showThreat(id);
                else A.modal.showAsset(id);
            });
        }
    });
};


/* ═══════════════════════════
   MAP FINDER
   ═══════════════════════════ */
A.findMap = function(){
    // Check common global names
    var names = ['amosMap','mosMap','map','tacticalMap','leafletMap'];
    for(var i=0;i<names.length;i++){
        var m = window[names[i]];
        if(m && m._leaflet_id && m.addLayer) return m;
    }
    // Search all Leaflet containers
    var els = document.querySelectorAll('.leaflet-container');
    for(var j=0;j<els.length;j++){
        var el = els[j];
        // Leaflet stores _leaflet_id on the element
        if(el._leaflet_id){
            // Find the map object that owns this container
            for(var wk in window){
                try{
                    var v = window[wk];
                    if(v && v._container === el && v.addLayer) return v;
                }catch(e){}
            }
        }
    }
    return null;
};


/* ═══════════════════════════
   MESH / COMM LINES
   ═══════════════════════════ */
var meshLines = [];
A.drawMesh = function(){
    var map = A.findMap();
    if(!map){console.warn('[AMOS] Mesh: no map found');return}

    // Clear old
    meshLines.forEach(function(l){try{map.removeLayer(l)}catch(e){}});
    meshLines = [];

    fetch('/api/phase3/metrics').then(function(r){return r.json()}).then(function(data){
        var assets = data.assets_detail || [];
        if(assets.length < 2) return;

        var ranges = {air:80, ground:30, maritime:50, awacs:150};

        for(var i=0;i<assets.length;i++){
            for(var j=i+1;j<assets.length;j++){
                var a=assets[i], b=assets[j];
                if(!a.lat||!b.lat) continue;
                var d = A.haversine(a.lat,a.lng,b.lat,b.lng);
                var maxR = Math.max(ranges[a.type]||30, ranges[b.type]||30);
                if(d <= maxR){
                    var q = 1-(d/maxR);
                    var color = q>0.6?'rgba(0,255,65,0.4)':q>0.3?'rgba(255,215,0,0.3)':'rgba(255,0,64,0.2)';
                    var w = q>0.6?2:1;
                    var line = L.polyline([[a.lat,a.lng],[b.lat,b.lng]],{
                        color:color,weight:w,dashArray:'4 6',className:'amos-mesh-line'
                    }).addTo(map);
                    line.bindTooltip(
                        '<b>'+(a.callsign||a.id)+' \u2194 '+(b.callsign||b.id)+'</b><br>'+
                        d.toFixed(1)+' km | Signal: '+(q*100).toFixed(0)+'%',
                        {className:'amos-mesh-tooltip',sticky:true}
                    );
                    meshLines.push(line);
                }
            }
        }
        console.log('[AMOS] Mesh: '+meshLines.length+' links');
    }).catch(function(e){console.warn('[AMOS] Mesh error:',e)});
};


/* ═══════════════════════════
   SWARM FORMATION PATTERNS
   ═══════════════════════════ */
var swarmPatternLines = [];
A.drawSwarmPattern = function(){
    var map = A.findMap();
    if(!map) return;

    // Clear old pattern lines
    swarmPatternLines.forEach(function(l){try{map.removeLayer(l)}catch(e){}});
    swarmPatternLines = [];

    fetch('/api/swarm').then(function(r){return r.json()}).then(function(data){
        if(!data || !data.formations) return;

        var fmts = data.formations || [];
        if(!Array.isArray(fmts)){
            // Maybe it's a dict keyed by formation name
            var arr = [];
            for(var k in fmts){ arr.push(Object.assign({name:k}, fmts[k])) }
            fmts = arr;
        }

        fmts.forEach(function(fm){
            var members = fm.members || fm.assets || [];
            if(members.length < 2) return;

            var pattern = (fm.pattern || fm.formation || fm.type || 'line').toLowerCase();
            var coords = members.map(function(m){return [m.lat||0, m.lng||0]}).filter(function(c){return c[0]!==0});
            if(coords.length < 2) return;

            var patternColor = {
                line: '#00ffff', diamond: '#ff00ff', wedge: '#ffaa00',
                column: '#00ffff', vee: '#ff00ff', spread: '#ffaa00',
                circle: '#00ff88', orbit: '#00ff88', stagger: '#ff8800'
            }[pattern] || '#00ffff';

            if(pattern === 'diamond' || pattern === 'circle'){
                // Close the shape
                coords.push(coords[0]);
            }

            var line = L.polyline(coords, {
                color: patternColor,
                weight: 2,
                dashArray: '8 6',
                opacity: 0.7,
                className: 'swarm-pattern-line'
            }).addTo(map);

            line.bindTooltip(
                '\u2B21 Swarm: <b>'+(fm.name||fm.id||'Formation')+'</b><br>'+
                'Pattern: '+pattern.toUpperCase()+'<br>'+
                'Members: '+members.length,
                {className:'amos-mesh-tooltip',sticky:true}
            );
            swarmPatternLines.push(line);
        });

        console.log('[AMOS] Swarm patterns: '+swarmPatternLines.length+' formations drawn');
    }).catch(function(e){});

    // Fallback: if /api/swarm doesn't have formations, draw from /api/assets
    fetch('/api/assets').then(function(r){return r.json()}).then(function(data){
        if(swarmPatternLines.length > 0) return; // Already drawn from /api/swarm
        var assets = Array.isArray(data) ? data : (data.assets ? (Array.isArray(data.assets) ? data.assets : Object.values(data.assets)) : Object.values(data));
        if(!assets || assets.length < 2) return;

        // Group by domain
        var groups = {};
        assets.forEach(function(a){
            var dom = (a.domain || a.type || 'unknown').toLowerCase();
            if(!groups[dom]) groups[dom] = [];
            if(a.lat && a.lng) groups[dom].push(a);
        });

        var domColors = {air:'#00ffff',ground:'#00ff41',maritime:'#4488ff',awacs:'#ffd700'};

        for(var dom in groups){
            var g = groups[dom];
            if(g.length < 2) continue;
            // Sort by longitude to make a clean line
            g.sort(function(a,b){return a.lng - b.lng});
            var coords = g.map(function(a){return [a.lat, a.lng]});
            var line = L.polyline(coords, {
                color: domColors[dom] || '#888',
                weight: 1.5,
                dashArray: '6 8',
                opacity: 0.5
            }).addTo(map);
            line.bindTooltip(dom.toUpperCase()+' formation ('+g.length+' assets)',{className:'amos-mesh-tooltip'});
            swarmPatternLines.push(line);
        }
        if(swarmPatternLines.length) console.log('[AMOS] Domain formation lines: '+swarmPatternLines.length);
    }).catch(function(e){});
};


/* ═══════════════════════════
   ALERTS POLLER (disabled — Phase 5 SocketIO amos_alerts is canonical)
   ═══════════════════════════ */
A.pollAlerts = function(){};  // No-op — real alerts via SocketIO


/* ═══════════════════════════
   HAVERSINE
   ═══════════════════════════ */
A.haversine = function(a,b,c,d){
    var R=6371, dL=(c-a)*Math.PI/180, dG=(d-b)*Math.PI/180;
    var x=Math.sin(dL/2)*Math.sin(dL/2)+Math.cos(a*Math.PI/180)*Math.cos(c*Math.PI/180)*Math.sin(dG/2)*Math.sin(dG/2);
    return R*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));
};


/* ═══════════════════════════
   CONTEXT MENU (right-click map)
   ═══════════════════════════ */
A.initContextMenu = function(){
    var map = A.findMap();
    if(!map) return;
    var menu = document.getElementById('amos-ctx-menu');
    if(!menu) return;

    map.on('contextmenu', function(e){
        e.originalEvent.preventDefault();
        var lat = e.latlng.lat.toFixed(5), lng = e.latlng.lng.toFixed(5);
        menu.innerHTML =
            '<div class="amos-ctx-item" onclick="AMOS.sendNearest('+lat+','+lng+')">Send Nearest Asset</div>'+
            '<div class="amos-ctx-item" onclick="AMOS.dropWaypoint('+lat+','+lng+')">Drop Waypoint</div>'+
            '<div class="amos-ctx-item" onclick="AMOS.toast(\''+lat+', '+lng+'\',\'info\')">Copy Coords</div>';
        menu.style.left = e.originalEvent.pageX+'px';
        menu.style.top = e.originalEvent.pageY+'px';
        menu.style.display = 'block';
    });

    document.addEventListener('click', function(){menu.style.display='none'});
};

A.sendNearest = function(lat,lng){
    fetch('/api/phase3/send_nearest',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({lat:lat,lng:lng})
    }).then(function(r){return r.json()}).then(function(d){
        A.toast('Dispatched: '+(d.asset||'?')+' ('+((d.dist||0)).toFixed(1)+'km)','success');
    });
};

A.dropWaypoint = function(lat,lng){
    var map = A.findMap();
    if(map && typeof L !== 'undefined'){
        L.circleMarker([lat,lng],{radius:6,color:'#ffd700',fillColor:'#ffd700',fillOpacity:0.8}).addTo(map)
         .bindTooltip('WP: '+lat.toFixed(4)+', '+lng.toFixed(4),{className:'amos-mesh-tooltip'});
        A.toast('Waypoint placed','info');
    }
};


/* ═══════════════════════════
   DOM CONTENT LOADED — INIT
   ═══════════════════════════ */
document.addEventListener('DOMContentLoaded', function(){
    console.log('[AMOS] DOMContentLoaded — initializing Phase 3');

    // Sorting
    A.initSorting();

    // Row click bindings
    A.bindRows();

    // Re-bind when tables update
    var obs = new MutationObserver(function(){
        setTimeout(function(){A.bindRows();A.initSorting()}, 300);
    });
    document.querySelectorAll('table tbody').forEach(function(tb){
        obs.observe(tb, {childList:true});
    });
    // Also watch for whole table replacements
    document.querySelectorAll('.table-responsive, [class*="table"]').forEach(function(el){
        obs.observe(el, {childList:true, subtree:true});
    });

    // Map-dependent features: retry until map is found
    var mapAttempts = 0;
    var mapTimer = setInterval(function(){
        mapAttempts++;
        var map = A.findMap();
        if(map){
            console.log('[AMOS] Map found on attempt '+mapAttempts);
            window.amosMap = map; // Expose globally
            A.drawMesh();
            A.drawSwarmPattern();
            A.initContextMenu();
            // Refresh mesh + patterns periodically
            setInterval(function(){A.drawMesh();A.drawSwarmPattern()}, 12000);
            clearInterval(mapTimer);
        } else if(mapAttempts >= 30){
            console.warn('[AMOS] No Leaflet map found after 30 attempts');
            clearInterval(mapTimer);
        }
    }, 1000);

    // Alert poller disabled — Phase 5 SocketIO handles all alerts

    console.log('[AMOS] Phase 3 init complete');
});

})();


/* ═══════════════════════════
   SWARM FORMATION CONTROLS
   ═══════════════════════════ */
(function(){
var A = window.AMOS = window.AMOS || {};
var formationLines = [];
var formationMarkers = [];

A.setFormation = function(pattern){
    var domain = document.getElementById('swarm-domain') || document.getElementById('c2-domain-filter');
    var domVal = domain ? domain.value : 'all';
    var statusEl = document.getElementById('swarm-status') || document.getElementById('c2-status');
    if(statusEl) statusEl.textContent = 'Setting ' + pattern.toUpperCase() + '...';

    // Highlight active button
    document.querySelectorAll('.swarm-btn').forEach(function(b){ b.classList.remove('active') });
    var activeBtn = document.getElementById('swarm-btn-' + pattern);
    if(activeBtn) activeBtn.classList.add('active');

    fetch('/api/swarm/formation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pattern: pattern, domain: domVal})
    })
    .then(function(r){ return r.json() })
    .then(function(data){
        if(data.error){
            A.toast('Swarm error: ' + data.error, 'error');
            if(statusEl) statusEl.textContent = 'Error: ' + data.error;
            return;
        }
        var cnt = data.count || (data.formation && data.formation.members ? data.formation.members.length : 0);
        A.toast('Formation: ' + pattern.toUpperCase() + ' (' + cnt + ' assets)', 'success');
        if(statusEl) statusEl.innerHTML = '<span style="color:#00ff41">' + pattern.toUpperCase() + '</span> — ' + cnt + ' assets moving';

        // ★ Draw formation paths on map ★
        if(data.formation && typeof A.drawFormationOnMap === 'function'){
            console.log('[SWARM] Drawing formation on map:', data.formation.pattern, data.formation.members ? data.formation.members.length : 0, 'members');
            A.drawFormationOnMap(data.formation);
        }
        // Also refresh domain pattern lines
        if(typeof A.drawSwarmPattern === 'function') A.drawSwarmPattern();
    })
    .catch(function(e){
        A.toast('Swarm error: ' + e.message, 'error');
        if(statusEl) statusEl.textContent = 'Error';
    });
};

A.clearFormation = function(){
    fetch('/api/swarm/formation/clear', {method:'POST'})
    .then(function(r){return r.json()})
    .then(function(d){
        A.toast('Formation cleared', 'info');
        var statusEl = document.getElementById('swarm-status') || document.getElementById('c2-status');
        if(statusEl) statusEl.textContent = 'No active formation';
        document.querySelectorAll('.swarm-btn').forEach(function(b){ b.classList.remove('active') });
        // Remove lines from map
        A._clearFormationLines();
    });
};

A._clearFormationLines = function(){
    var map = A.findMap();
    if(!map) return;
    formationLines.forEach(function(l){ try{map.removeLayer(l)}catch(e){} });
    formationMarkers.forEach(function(m){ try{map.removeLayer(m)}catch(e){} });
    formationLines = [];
    formationMarkers = [];
};

A.drawFormationOnMap = function(formation){
    var map = A.findMap();
    if(!map || !formation || !formation.members || formation.members.length < 2) return;

    A._clearFormationLines();

    var pattern = formation.pattern || 'line';
    var members = formation.members;

    var patternColors = {
        line:    '#00ffff',
        diamond: '#ff00ff',
        wedge:   '#ffaa00',
        vee:     '#ffaa00',
        column:  '#00ffff',
        spread:  '#88ff00',
        orbit:   '#ff8800'
    };
    var color = patternColors[pattern] || '#00ffff';

    // Draw current→formation waypoint lines (movement arrows)
    members.forEach(function(m){
        if(!m.lat || !m.formation_lat) return;

        // Dashed line from current position to formation position
        var moveLine = L.polyline(
            [[m.lat, m.lng], [m.formation_lat, m.formation_lng]],
            { color: color, weight: 2, dashArray: '6 4', opacity: 0.7, className: 'swarm-pattern-line' }
        ).addTo(map);
        formationLines.push(moveLine);

        // Formation position marker (hollow circle)
        var fmMarker = L.circleMarker(
            [m.formation_lat, m.formation_lng],
            { radius: 6, color: color, fillColor: color, fillOpacity: 0.2, weight: 2 }
        ).addTo(map);
        fmMarker.bindTooltip(
            '<b>' + (m.callsign || m.id) + '</b><br>Formation: ' + pattern.toUpperCase(),
            { className: 'amos-mesh-tooltip' }
        );
        formationMarkers.push(fmMarker);
    });

    // Draw the formation shape outline
    var fmCoords = members.map(function(m){
        return [m.formation_lat || m.lat, m.formation_lng || m.lng];
    }).filter(function(c){ return c[0] !== 0; });

    if(pattern === 'diamond' || pattern === 'orbit'){
        // Close the shape
        fmCoords.push(fmCoords[0]);
    }

    if(fmCoords.length >= 2){
        var outline = L.polyline(fmCoords, {
            color: color, weight: 3, opacity: 0.9,
            dashArray: pattern === 'orbit' ? '12 6' : null
        }).addTo(map);
        outline.bindTooltip(
            '<b>\u2B21 ' + pattern.toUpperCase() + ' FORMATION</b><br>' + members.length + ' assets',
            { className: 'amos-mesh-tooltip', sticky: true }
        );
        formationLines.push(outline);
    }

    // Draw center marker
    if(formation.center){
        var center = L.circleMarker(
            [formation.center.lat, formation.center.lng],
            { radius: 4, color: '#fff', fillColor: '#fff', fillOpacity: 0.8, weight: 1 }
        ).addTo(map);
        center.bindTooltip('Formation Center', {className:'amos-mesh-tooltip'});
        formationMarkers.push(center);
    }

    console.log('[AMOS] Formation drawn: ' + pattern + ' with ' + members.length + ' assets, ' + formationLines.length + ' lines');
};

// Auto-load any existing formation on page load
setTimeout(function(){
    fetch('/api/swarm/formation').then(function(r){return r.json()}).then(function(f){
        if(f && f.pattern){
            A.drawFormationOnMap(f);
            var statusEl = document.getElementById('swarm-status') || document.getElementById('c2-status');
            if(statusEl) statusEl.innerHTML = '<span style="color:#00ff41">' + f.pattern.toUpperCase() + '</span> — ' + (f.members||[]).length + ' assets';
            var btn = document.getElementById('swarm-btn-' + f.pattern);
            if(btn) btn.classList.add('active');
        }
    }).catch(function(e){});
}, 3000);

})();
