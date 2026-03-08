"""AMOS Phase 3 — API Routes Blueprint (patched for live state)"""
from flask import Blueprint, jsonify, request, current_app
import random, time, math
from datetime import datetime

phase3_bp = Blueprint('phase3', __name__, url_prefix='/api/phase3')

_state_getter = None
_alerts = []
_alert_ctr = 0
_missions = []

def init_phase3(getter_fn):
    """Accept a callable that returns {'assets': dict, 'threats': list, 'events': list}"""
    global _state_getter
    _state_getter = getter_fn
    print("[AMOS] Phase 3 state getter registered")

def _state():
    if callable(_state_getter):
        return _state_getter()
    if isinstance(_state_getter, dict):
        return _state_getter
    return {}

def _assets():
    s = _state()
    a = s.get('assets', {})
    if isinstance(a, list):
        return {str(x.get('id', i)): x for i, x in enumerate(a)}
    return a if isinstance(a, dict) else {}

def _threats():
    s = _state()
    t = s.get('threats', [])
    return t if isinstance(t, list) else list(t.values()) if isinstance(t, dict) else []

def _events():
    return _state().get('events', [])

def _alert(msg, sev='info'):
    global _alert_ctr
    _alert_ctr += 1
    _alerts.append({'id': _alert_ctr, 'message': msg, 'severity': sev,
                     'time': datetime.now().strftime('%H:%M:%S'), 'ts': time.time()})
    if len(_alerts) > 200:
        del _alerts[:100]

def _hav(a, b, c, d):
    R = 6371
    dL, dG = math.radians(c - a), math.radians(d - b)
    x = math.sin(dL/2)**2 + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(dG/2)**2
    return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))

# ---- ASSET DETAIL ----
@phase3_bp.route('/asset/<asset_id>')
def asset_detail(asset_id):
    assets = _assets()
    a = assets.get(asset_id)
    if not a:
        lo = asset_id.lower().replace('-','').replace('_','')
        for k, v in assets.items():
            kn = k.lower().replace('-','').replace('_','')
            cn = str(v.get('callsign','')).lower().replace('-','').replace('_','')
            nn = str(v.get('name','')).lower().replace('-','').replace('_','')
            idn = str(v.get('id','')).lower().replace('-','').replace('_','')
            if lo == kn or lo == cn or lo == nn or lo == idn or lo in kn or lo in cn or lo in nn:
                a = v; break
    if not a:
        return jsonify({'error': 'not found', 'searched': asset_id, 'available': list(assets.keys())[:10]}), 404
    out = dict(a)
    out.setdefault('id', asset_id)
    out.setdefault('health', 100)
    out.setdefault('battery', 100)
    out.setdefault('autonomy', 2)
    out.setdefault('sensors', [])
    out.setdefault('weapons', [])
    return jsonify(out)

# ---- THREAT DETAIL ----
@phase3_bp.route('/threat/<threat_id>')
def threat_detail(threat_id):
    for t in _threats():
        tid = str(t.get('id', ''))
        ttype = str(t.get('type', ''))
        if tid == threat_id or ttype == threat_id or threat_id.lower() in tid.lower() or threat_id.lower() in ttype.lower():
            mn = None
            for a in _assets().values():
                if a.get('lat') and t.get('lat'):
                    d = _hav(a['lat'], a['lng'], t['lat'], t['lng'])
                    if mn is None or d < mn: mn = d
            out = dict(t)
            out['nearest_dist'] = mn
            sc = t.get('threat_score', 0.5)
            if sc > 0.8:
                out['recommended_coa'] = 'IMMEDIATE ENGAGEMENT — High threat. Recommend kinetic or EW response.'
            elif sc > 0.5:
                out['recommended_coa'] = 'ACTIVE TRACKING — Monitor and prepare countermeasures.'
            else:
                out['recommended_coa'] = 'PASSIVE MONITORING — Low threat. Continue ISR.'
            return jsonify(out)
    return jsonify({'error': 'not found', 'searched': threat_id}), 404

# ---- TASK ASSET ----
@phase3_bp.route('/asset/<asset_id>/task', methods=['POST'])
def task_asset(asset_id):
    a = _assets().get(asset_id)
    if not a:
        for k, v in _assets().items():
            if asset_id.lower() in k.lower() or asset_id.lower() in str(v.get('callsign','')).lower():
                a = v; break
    if not a: return jsonify({'error': 'not found'}), 404
    d = request.get_json() or {}
    task = d.get('task', '')
    if task == 'rtb':
        a['status'] = 'rtb'; a['waypoints'] = [{'lat': 35.689, 'lng': 51.312}]
        _alert(f'{a.get("callsign", asset_id)} RTB', 'info')
    elif task == 'orbit':
        a['status'] = 'orbiting'; _alert(f'{a.get("callsign", asset_id)} orbiting', 'info')
    elif task == 'set_autonomy':
        a['autonomy'] = d.get('autonomy', 0)
        _alert(f'{a.get("callsign", asset_id)} autonomy → T{a["autonomy"]}', 'warning' if a['autonomy'] >= 4 else 'info')
    elif task == 'hold':
        a['status'] = 'holding'
    return jsonify({'status': 'ok', 'task': task})

# ---- ENGAGE ----
@phase3_bp.route('/engage', methods=['POST'])
def engage():
    d = request.get_json() or {}
    tid, act = d.get('threat_id'), d.get('action', 'track')
    for t in _threats():
        if str(t.get('id','')) == tid or tid.lower() in str(t.get('type','')).lower():
            t['status'] = {'track':'tracking','jam':'jammed','engage':'engaged','cyber_block':'blocked'}.get(act, act)
            _alert(f'{act.upper()} on {tid}', 'critical' if act == 'engage' else 'warning')
            return jsonify({'status': 'approved', 'action': act})
    return jsonify({'error': 'not found'}), 404

# ---- SEND / TASK NEAREST ----
@phase3_bp.route('/send_nearest', methods=['POST'])
def send_nearest():
    d = request.get_json() or {}
    lat, lng = d.get('lat', 0), d.get('lng', 0)
    best, bd = None, float('inf')
    for a in _assets().values():
        if a.get('lat'):
            dd = _hav(a['lat'], a['lng'], lat, lng)
            if dd < bd: bd = dd; best = a
    if best:
        best['waypoints'] = [{'lat': lat, 'lng': lng}]; best['status'] = 'enroute'
        _alert(f'{best.get("callsign", best.get("id"))} dispatched', 'success')
        return jsonify({'asset': best.get('callsign', best.get('id')), 'dist': bd})
    return jsonify({'error': 'none'}), 404

@phase3_bp.route('/task_nearest', methods=['POST'])
def task_nearest():
    d = request.get_json() or {}
    lat, lng, task = d.get('lat',0), d.get('lng',0), d.get('task','orbit')
    best, bd = None, float('inf')
    for a in _assets().values():
        if a.get('lat'):
            dd = _hav(a['lat'], a['lng'], lat, lng)
            if dd < bd: bd = dd; best = a
    if best:
        best['status'] = task
        return jsonify({'asset': best.get('callsign', best.get('id'))})
    return jsonify({'error': 'none'}), 404

# ---- ALL ASSETS (for mesh / table binding) ----
@phase3_bp.route('/assets')
def all_assets():
    return jsonify(_assets())

# ---- ALL THREATS ----
@phase3_bp.route('/threats')
def all_threats():
    return jsonify(_threats())

# ---- METRICS ----
@phase3_bp.route('/metrics')
def metrics():
    assets = _assets(); threats = _threats(); events = _events()
    al = list(assets.values()) if isinstance(assets, dict) else list(assets)
    neut = sum(1 for t in threats if t.get('status') in ('neutralized','jammed','blocked','engaged'))
    act = sum(1 for t in threats if t.get('status','active') == 'active')
    trk = sum(1 for t in threats if t.get('status') == 'tracking')
    labels = [a.get('callsign', a.get('id','?'))[:10] for a in al[:20]]
    health = [a.get('health', 100) for a in al[:20]]
    batt = [a.get('battery', 100) for a in al[:20]]
    now = time.time()
    et = [datetime.fromtimestamp(now - (9-i)*30).strftime('%H:%M') for i in range(10)]
    ec = [random.randint(0, 5) for i in range(10)]
    return jsonify({
        'threats_neutralized': neut, 'threats_active': act, 'threats_tracking': trk,
        'asset_labels': labels, 'asset_health': health, 'asset_battery': batt,
        'event_times': et, 'event_counts': ec,
        'assets_detail': [{'id':a.get('id',k),'callsign':a.get('callsign',a.get('name','')),'type':a.get('type',''),
            'health':a.get('health',100),'battery':a.get('battery',100),'lat':a.get('lat',0),'lng':a.get('lng',0),
            'alt':a.get('alt',0),'speed':a.get('speed',0),'heading':a.get('heading',0),
            'autonomy':a.get('autonomy',0),'status':a.get('status','active')} for k,a in (assets.items() if isinstance(assets,dict) else enumerate(assets))]
    })

# ---- KILL CHAIN ----
@phase3_bp.route('/killchain')
def killchain():
    for t in _threats():
        if t.get('status') in ('tracking','jammed','engaged'):
            stage = {'tracking':'TRACK','jammed':'TARGET','engaged':'ENGAGE'}.get(t['status'],'FIND')
            return jsonify({'active_engagement': {'threat_id': t.get('id'), 'stage': stage}})
    return jsonify({'active_engagement': {'threat_id':'scan','stage':random.choice(['FIND','FIX','TRACK'])}})

# ---- ALERTS ----
# NOTE: Random demo alerts removed — Phase 5 SocketIO amos_alerts is the canonical alert system.
# This endpoint now only returns action-triggered alerts (engage, dispatch, etc.)
@phase3_bp.route('/alerts')
def alerts():
    since = int(request.args.get('since', 0))
    new = [a for a in _alerts if a['id'] > since]
    return jsonify(new[-5:])

# ---- EW SPECTRUM ----
@phase3_bp.route('/ew/spectrum')
def ew_spectrum():
    ems = [
        {'freq_mhz':430,'power_dbm':-40+random.uniform(-3,3),'bandwidth':15,'type':'RADAR'},
        {'freq_mhz':900,'power_dbm':-55+random.uniform(-3,3),'bandwidth':25,'type':'COMMS'},
        {'freq_mhz':1575,'power_dbm':-60+random.uniform(-3,3),'bandwidth':20,'type':'GPS'},
        {'freq_mhz':2400,'power_dbm':-35+random.uniform(-3,3),'bandwidth':40,'type':'WIFI'},
        {'freq_mhz':3500,'power_dbm':-50+random.uniform(-3,3),'bandwidth':30,'type':'C-BAND'},
        {'freq_mhz':5800,'power_dbm':-45+random.uniform(-3,3),'bandwidth':20,'type':'DRONE-C2'},
    ]
    if random.random() < 0.3:
        ems.append({'freq_mhz':random.randint(100,5900),'power_dbm':random.uniform(-70,-30),'bandwidth':random.randint(5,40),'type':'UNKNOWN'})
    jams = [{'start_mhz':2380,'end_mhz':2450}] if any(t.get('status')=='jammed' for t in _threats()) else []
    return jsonify({'emitters': ems, 'jamming': jams})

# ---- CYBER TOPOLOGY ----
@phase3_bp.route('/cyber/topology')
def cyber_topology():
    comp = random.random() < 0.25
    nodes = [
        {'id':'hq','name':'HQ-NET','status':'secure'},{'id':'mesh1','name':'MESH-1','status':'secure'},
        {'id':'mesh2','name':'MESH-2','status':'secure'},{'id':'sat','name':'SAT-COM','status':'secure'},
        {'id':'gnd','name':'GND-CTRL','status':'secure'},{'id':'air','name':'AIR-NET','status':'secure'},
        {'id':'ew','name':'EW-NODE','status':'secure'},{'id':'sig','name':'SIGINT','status':'secure'},
        {'id':'ext','name':'EXTERN','status':'warning','compromised':comp},
    ]
    links = [
        {'from':'hq','to':'mesh1','active':True},{'from':'hq','to':'mesh2','active':True},
        {'from':'hq','to':'sat','active':True},{'from':'mesh1','to':'gnd','active':True},
        {'from':'mesh1','to':'air','active':True},{'from':'mesh2','to':'ew','active':True},
        {'from':'mesh2','to':'sig','active':True},{'from':'sat','to':'air','active':True},
        {'from':'ext','to':'hq','active':True,'attack':comp},
    ]
    return jsonify({'nodes': nodes, 'links': links})

# ---- AAR TIMELINE ----
@phase3_bp.route('/aar/timeline')
def aar_timeline():
    evts = _events()
    if evts and len(evts) > 0:
        return jsonify([{'time':e.get('time',datetime.fromtimestamp(e.get('timestamp',time.time())).strftime('%H:%M:%S')),
            'title':e.get('title',e.get('type','Event')),'description':e.get('description',e.get('message','')),
            'type':e.get('category',e.get('type','info'))} for e in evts[-50:]])
    now = time.time()
    demo = [
        ('threat','Hostile Drone Detected','UAV signature bearing 045, range 15km'),
        ('ew','EW Scan Initiated','Full spectrum sweep 100MHz-6GHz'),
        ('movement','Reaper-1 Repositioned','Moving to intercept vector'),
        ('threat','Threat Classified','Commercial drone, possible ISR platform'),
        ('ew','Jamming Authorized','2.4GHz band jam active'),
        ('cyber','Cyber Probe Detected','Port scan on mesh from unknown source'),
        ('cyber','Firewall Block','Probe blocked, source isolated'),
        ('movement','Ground-4 Repositioned','Moving to overwatch position'),
        ('threat','Threat Neutralized','Hostile drone lost C2 link'),
        ('ew','Jam Ceased','EW returned to passive'),
    ]
    return jsonify([{'time':datetime.fromtimestamp(now-(len(demo)-i)*120).strftime('%H:%M:%S'),
        'title':t,'description':d,'type':tp} for i,(tp,t,d) in enumerate(demo)])

# ---- MISSION PLAN ----
@phase3_bp.route('/mission/plan', methods=['POST'])
def save_mission():
    d = request.get_json() or {}
    mid = f"MSN-{len(_missions)+1:03d}"
    _missions.append({'id':mid,'asset':d.get('asset_id'),'wps':d.get('waypoints',[]),'time':datetime.now().isoformat()})
    aid = d.get('asset_id')
    if aid:
        a = _assets().get(aid)
        if a: a['waypoints'] = d.get('waypoints',[]); a['status'] = 'enroute'; _alert(f'{mid} assigned to {a.get("callsign",aid)}','success')
    return jsonify({'mission_id': mid, 'status': 'saved'})
