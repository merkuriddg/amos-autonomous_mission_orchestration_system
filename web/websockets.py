"""AMOS WebSocket Handlers — Multi-operator presence, chat, asset locks."""

from flask import session, request
from web.extensions import socketio
from web.state import (
    online_ops, asset_locks, USERS,
    db_execute, now_iso,
)

_OP_COLORS = ["#00ff41", "#4488ff", "#ff4444", "#ffaa00", "#ff66ff", "#00cccc", "#ff8800", "#88ff00"]


def _broadcast_presence():
    """Send current operator list to all connected clients."""
    ops = []
    for sid, info in online_ops.items():
        ops.append({"user": info["user"], "name": info["name"], "role": info["role"],
                    "page": info.get("page", ""), "color": info.get("color", "#888")})
    socketio.emit("operator_presence", ops)


def register_websockets(sio):
    """Register all SocketIO event handlers."""

    @sio.on("connect")
    def ws_connect():
        """Track operator connection."""
        u = session.get("user")
        if not u:
            return
        info = USERS.get(u, {})
        color_idx = len(online_ops) % len(_OP_COLORS)
        online_ops[request.sid] = {
            "user": u, "name": info.get("name", u), "role": info.get("role", ""),
            "page": "", "cursor": None, "color": _OP_COLORS[color_idx],
            "connected_at": now_iso()
        }
        _broadcast_presence()

    @sio.on("disconnect")
    def ws_disconnect():
        """Clean up on disconnect."""
        sid = request.sid
        op = online_ops.pop(sid, None)
        if op:
            to_unlock = [aid for aid, lk in asset_locks.items() if lk["locked_by"] == op["user"]]
            for aid in to_unlock:
                asset_locks.pop(aid, None)
            _broadcast_presence()
            sio.emit("asset_locks", asset_locks)

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
