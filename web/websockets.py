"""AMOS WebSocket Handlers — Multi-operator presence, chat, asset locks."""

from flask import session, request
from web.extensions import socketio
from web.state import (
    online_ops, asset_locks, USERS,
    db_execute, now_iso,
)

_OP_COLORS = ["#00ff41", "#4488ff", "#ff4444", "#ffaa00", "#ff66ff", "#00cccc", "#ff8800", "#88ff00"]

# Domain-to-room mapping for role-based filtering
_DOMAIN_ROOMS = {
    "air": "domain_air",
    "ground": "domain_ground",
    "maritime": "domain_maritime",
    "all": "domain_all",
}


def _broadcast_presence():
    """Send current operator list to all connected clients."""
    ops = []
    for sid, info in online_ops.items():
        ops.append({"user": info["user"], "name": info["name"], "role": info["role"],
                    "domain": info.get("domain", "all"),
                    "page": info.get("page", ""), "color": info.get("color", "#888")})
    socketio.emit("operator_presence", ops)


def broadcast_state_diff(diff_type, data, domain=None):
    """Broadcast a state change to connected clients.

    If domain is specified, only operators in that domain (or 'all') receive it.
    """
    payload = {"type": diff_type, "data": data, "timestamp": now_iso()}
    if domain and domain != "all":
        room = _DOMAIN_ROOMS.get(domain)
        if room:
            socketio.emit("state_diff", payload, room=room)
        # Always also send to commanders/observers (domain_all)
        socketio.emit("state_diff", payload, room="domain_all")
    else:
        socketio.emit("state_diff", payload)


def register_websockets(sio):
    """Register all SocketIO event handlers."""

    @sio.on("connect")
    def ws_connect():
        """Track operator connection and join domain room."""
        from flask_socketio import join_room
        u = session.get("user")
        if not u:
            return
        info = USERS.get(u, {})
        domain = info.get("domain", "all")
        color_idx = len(online_ops) % len(_OP_COLORS)
        online_ops[request.sid] = {
            "user": u, "name": info.get("name", u), "role": info.get("role", ""),
            "domain": domain,
            "page": "", "cursor": None, "color": _OP_COLORS[color_idx],
            "connected_at": now_iso()
        }
        # Join domain-specific room for filtered broadcasts
        room = _DOMAIN_ROOMS.get(domain, "domain_all")
        join_room(room)
        if domain != "all":
            join_room("domain_all")  # commanders see everything
        _broadcast_presence()
        # Send current lock state to new client
        sio.emit("asset_locks", asset_locks, room=request.sid)

    @sio.on("disconnect")
    def ws_disconnect():
        """Clean up on disconnect."""
        from flask_socketio import leave_room
        sid = request.sid
        op = online_ops.pop(sid, None)
        if op:
            to_unlock = [aid for aid, lk in asset_locks.items() if lk["locked_by"] == op["user"]]
            for aid in to_unlock:
                asset_locks.pop(aid, None)
            domain = op.get("domain", "all")
            room = _DOMAIN_ROOMS.get(domain, "domain_all")
            leave_room(room)
            if domain != "all":
                leave_room("domain_all")
            _broadcast_presence()
            sio.emit("asset_locks", asset_locks)

    @sio.on("state_annotation")
    def ws_state_annotation(data):
        """Operator annotates the shared map (drawing, marker, etc.)."""
        sid = request.sid
        op = online_ops.get(sid)
        if not op:
            return
        annotation = {
            "user": op["user"], "name": op["name"], "color": op["color"],
            "type": data.get("type", "marker"),  # marker, line, polygon, text
            "geometry": data.get("geometry", {}),
            "label": data.get("label", ""),
            "timestamp": now_iso(),
        }
        sio.emit("annotation", annotation, include_self=False)

    @sio.on("operator_page")
    def ws_operator_page(data):
        """Operator reports which page they're viewing."""
        sid = request.sid
        if sid in online_ops:
            online_ops[sid]["page"] = data.get("page", "")
            _broadcast_presence()

    @sio.on("operator_cursor")
    def ws_operator_cursor(data):
        """Relay cursor position to all other operators."""
        sid = request.sid
        op = online_ops.get(sid)
        if not op:
            return
        op["cursor"] = {"lat": data.get("lat"), "lng": data.get("lng")}
        sio.emit("cursor_update", {
            "user": op["user"], "name": op["name"], "color": op["color"],
            "lat": data.get("lat"), "lng": data.get("lng")
        }, include_self=False)

    @sio.on("team_chat")
    def ws_team_chat(data):
        """Broadcast a chat message and persist it."""
        sid = request.sid
        op = online_ops.get(sid)
        u = op["user"] if op else session.get("user", "anonymous")
        name = op["name"] if op else u
        channel = data.get("channel", "general")
        msg = (data.get("message", "") or "").strip()
        if not msg:
            return
        try:
            db_execute("INSERT INTO chat_messages (channel, sender, message) VALUES(%s,%s,%s)",
                       (channel, u, msg))
        except Exception:
            pass
        sio.emit("chat_message", {
            "channel": channel, "sender": u, "name": name,
            "message": msg, "timestamp": now_iso(),
            "color": op.get("color", "#888") if op else "#888"
        })

    @sio.on("asset_lock")
    def ws_asset_lock(data):
        """Lock an asset for exclusive control."""
        sid = request.sid
        op = online_ops.get(sid)
        if not op:
            return
        aid = data.get("asset_id", "").strip().upper()
        if not aid:
            return
        existing = asset_locks.get(aid)
        if existing and existing["locked_by"] != op["user"]:
            sio.emit("lock_denied", {"asset_id": aid, "locked_by": existing["locked_by"]})
            return
        asset_locks[aid] = {"locked_by": op["user"], "locked_at": now_iso()}
        try:
            db_execute(
                "INSERT INTO asset_locks (asset_id, locked_by) VALUES(%s,%s) "
                "ON DUPLICATE KEY UPDATE locked_by=%s, locked_at=CURRENT_TIMESTAMP",
                (aid, op["user"], op["user"]))
        except Exception:
            pass
        sio.emit("asset_locks", asset_locks)

    @sio.on("asset_unlock")
    def ws_asset_unlock(data):
        """Release an asset lock."""
        sid = request.sid
        op = online_ops.get(sid)
        if not op:
            return
        aid = data.get("asset_id", "").strip().upper()
        existing = asset_locks.get(aid)
        if existing and existing["locked_by"] == op["user"]:
            asset_locks.pop(aid, None)
            try:
                db_execute("DELETE FROM asset_locks WHERE asset_id=%s", (aid,))
            except Exception:
                pass
        sio.emit("asset_locks", asset_locks)
