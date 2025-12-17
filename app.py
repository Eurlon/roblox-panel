from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet
from datetime import datetime

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# CONFIGURATION
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_kicks = {}
pending_commands = {}
history_logs = []

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

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ROBLOX CONTROL PANEL PRO</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh}
.container{max-width:1600px;margin:auto;padding:40px}
h1{font-family:Orbitron;font-size:3rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}

.main-layout{display:grid;grid-template-columns: 1fr 400px; gap:30px}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;box-shadow:0 0 30px rgba(0,0,0,.7);position:relative;transition:transform .3s}
.card:hover{transform:translateY(-5px)}

.trash-player{position:absolute;top:15px;right:15px;background:none;border:none;color:#444;cursor:pointer;font-size:1.2rem;transition:0.2s}
.trash-player:hover{color:#ff3366;transform:scale(1.2)}

.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:14px;height:14px;border-radius:50%;background:red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}

.name{font-size:1.6rem;font-weight:600;color:#ffcc00;margin-bottom:10px}
.info{font-size:0.9rem;color:#aaa;margin-bottom:20px;line-height:1.4}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:1rem;text-transform:uppercase}

button.kick-btn{padding:10px;border:none;border-radius:10px;cursor:pointer;font-weight:bold;font-size:0.85rem;color:white;transition:transform .2s;margin-bottom:5px}
button.kick-btn:hover{transform:scale(1.05);filter:brightness(1.2)}

/* HISTORY SECTION */
.history-panel{background:rgba(10,10,10,0.9);border:1px solid #222;border-radius:18px;padding:20px;height:750px;display:flex;flex-direction:column}
.history-list{flex-grow:1;overflow-y:auto;font-size:0.85rem}
.history-item{padding:10px;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
.hist-time{color:#555;font-family:monospace;margin-right:10px}
.hist-user{color:#00ffaa;font-weight:bold}
.del-hist{color:#444;cursor:pointer;font-weight:bold}
.del-hist:hover{color:#ff3366}

/* MODALS */
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:450px;box-shadow:0 0 40px rgba(0,255,170,0.2)}
.modal-content input{width:100%;padding:15px;border-radius:12px;border:none;background:#222;color:white;margin-bottom:20px}
.modal-buttons{display:flex;gap:15px}
.modal-buttons button{flex:1;padding:12px;border:none;border-radius:12px;font-weight:bold;cursor:pointer}
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
                <h2 class="category" style="margin-top:0">Activity History</h2>
                <button onclick="clearHistory()" style="background:none;border:none;color:#555;cursor:pointer;font-size:0.8rem">CLEAR ALL</button>
            </div>
            <div class="history-panel">
                <div class="history-list" id="history-list"></div>
            </div>
        </div>
    </div>
</div>

<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2 style="color:#ff3366;margin-bottom:15px">Kick Player</h2>
        <input type="text" id="kickReason" placeholder="Reason (optional)">
        <div class="modal-buttons">
            <button style="background:#333;color:white" onclick="closeModal('kickModal')">Cancel</button>
            <button style="background:#ff3366;color:white" id="confirmKickBtn">Confirm Kick</button>
        </div>
    </div>
</div>

<div class="modal" id="soundModal">
    <div class="modal-content">
        <h2 style="color:orange;margin-bottom:15px">Play Sound</h2>
        <input type="text" id="soundAssetId" placeholder="Asset ID (ex: 123456)">
        <div class="modal-buttons">
            <button style="background:#333;color:white" onclick="closeModal('soundModal')">Cancel</button>
            <button style="background:orange;color:white" id="confirmSoundBtn">Play Asset</button>
        </div>
    </div>
</div>

<script>
const socket = io();
let selectedUid = null;

// GESTION DES MODALES
function openKickModal(uid) { selectedUid = uid; document.getElementById('kickModal').classList.add('active'); }
function openSoundModal(uid) { selectedUid = uid; document.getElementById('soundModal').classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); selectedUid = null; }

// ACTIONS
function deletePlayer(uid) {
    fetch("/delete_player", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: uid})});
}

function sendTroll(uid, cmd, assetId = null) {
    const body = {userid: uid, cmd: cmd};
    if(assetId) body.assetId = assetId;
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
}

document.getElementById('confirmKickBtn').onclick = () => {
    const reason = document.getElementById('kickReason').value || "Kicked by Admin";
    sendTroll(selectedUid, 'kick', reason);
    closeModal('kickModal');
};

document.getElementById('confirmSoundBtn').onclick = () => {
    const assetId = document.getElementById('soundAssetId').value;
    if(assetId) sendTroll(selectedUid, 'playsound', assetId);
    closeModal('soundModal');
};

function clearHistory() { fetch("/clear_history", {method: "POST"}); }
function deleteLog(id) { fetch("/clear_history", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({log_id: id})}); }

// RENDU
socket.on("update", (data) => {
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));

    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) {
            card = document.createElement("div");
            card.className = "card";
            card.id = `card_${id}`;
            grid.appendChild(card);
        }
        card.innerHTML = `
            <button class="trash-player" onclick="deletePlayer('${id}')">🗑️</button>
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name">${p.username}</div>
            <div class="info">ID: ${id}<br>Executor: ${p.executor}<br>GameID: ${p.gameId}</div>
            
            <div class="category">Trolls</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588);" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff00ff,#aa00aa);" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#00ffff,#00aaaa);" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ffff00,#aaaa00);color:#000" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#88ff88,#55aa55);color:#000" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff5555,#aa0000);" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#5555ff,#0000aa);" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="kick-btn" style="background:orange;" onclick="openSoundModal('${id}')">PLAY SOUND</button>
            </div>

            <div class="category">Undo</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="kick-btn" style="background:#444;" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
            </div>
        `;
    });

    document.querySelectorAll('.card').forEach(c => {
        if (!currentIds.has(c.id.replace('card_', ''))) c.remove();
    });
});

socket.on("update_history", (logs) => {
    const list = document.getElementById("history-list");
    list.innerHTML = logs.map(log => `
        <div class="history-item">
            <div><span class="hist-time">[${log.time}]</span><span class="hist-user">${log.user}</span>: ${log.action}</div>
            <div class="del-hist" onclick="deleteLog('${log.id}')">✕</div>
        </div>
    `).join('');
});
</script>
</body>
</html>
"""

# ROUTES PYTHON
@app.route("/")
def index():
    check_ip()
    return render_template_string(HTML)

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
                "executor": d.get("executor", "Unknown"),
                "gameId": d.get("gameId", "N/A"),
                "last": now,
                "online": True
            }
        elif d.get("action") == "heartbeat" and uid in connected_players:
            connected_players[uid]["last"] = now
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid", ""))
        if uid in pending_commands:
            cmd_data = pending_commands.pop(uid)
            if isinstance(cmd_data, dict):
                return jsonify({"command": cmd_data['cmd'], "assetId": cmd_data.get('assetId')})
            return jsonify({"command": cmd_data})
        return jsonify({})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd = str(d["userid"]), d["cmd"]
    assetId = d.get("assetId")
    
    if assetId:
        pending_commands[uid] = {"cmd": cmd, "assetId": assetId}
    else:
        pending_commands[uid] = cmd

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
        add_to_history("Panel: Supprimé", name)
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
            if now - p["last"] > 120: to_remove.append(uid)
        for uid in to_remove:
            name = connected_players[uid]["username"]
            del connected_players[uid]
            add_to_history("Timeout", name)
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
