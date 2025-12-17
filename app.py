from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_kicks = {}
pending_commands = {}
action_history = []  # Nouvel historique global

def log_action(action_type, username, userid, details=""):
    timestamp = time.strftime("%H:%M:%S")
    action_history.append({
        "time": timestamp,
        "type": action_type,
        "username": username,
        "userid": userid,
        "details": details
    })
    # Garder seulement les 100 dernières actions
    if len(action_history) > 100:
        action_history.pop(0)
    socketio.emit("history_update", action_history)

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
    <html><body style="background:#000;color:#ff3366;font-family:Arial;text-align:center;padding-top:15%;">
        <h1>Accès refusé</h1><p>Ta cru quoi fdp ?</p><p>Ton IP : <b>{detected}</b></p>
    </body></html>
    """, 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll", "/delete_player", "/clear_history", "/delete_history_item"]:
        check_ip()

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>ROBLOX CONTROL PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh}
.container{max-width:1400px;margin:auto;padding:40px}
h1{font-family:Orbitron;font-size:3.5rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}
.stats{text-align:center;margin:30px 0;font-size:1.8rem}
.tabs{margin:20px 0;display:flex;gap:15px;justify-content:center;flex-wrap:wrap}
.tab-btn{padding:12px 30px;background:#111;border:2px solid #333;border-radius:12px;cursor:pointer;font-weight:bold;transition:all .3s}
.tab-btn.active{border-color:#00ffaa;background:#003322;color:#00ffaa}
.tab-content{display:none}
.tab-content.active{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}
.card{background:rgba(20,20,20,.95);border-radius:18px;padding:25px;position:relative;box-shadow:0 0 30px rgba(0,0,0,.7);transition:transform .3s}
.card:hover{transform:translateY(-8px)}
.delete-player{position:absolute;top:12px;right:12px;background:#ff3366;color:white;width:36px;height:36px;border-radius:50%;border:none;cursor:pointer;font-size:18px;font-weight:bold;opacity:0.8}
.delete-player:hover{opacity:1;transform:scale(1.1)}
.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:14px;height:14px;border-radius:50%;background:red;box-shadow:0 0 12px red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}
.name{font-size:1.8rem;font-weight:600;color:#ffcc00;margin-bottom:10px}
.name a{color:#ffcc00;text-decoration:none}
.info{font-size:1rem;color:#aaa;margin-bottom:20px;line-height:1.6}
.category{font-weight:bold;color:#00ffaa;margin:18px 0 12px;font-size:1.15rem;text-shadow:0 0 10px #00ffaa}
button.kick-btn{padding:12px;border:none;border-radius:12px;cursor:pointer;font-weight:bold;font-size:0.95rem;color:white;transition:all .2s;margin:4px 0}
button.kick-btn:hover{transform:scale(1.05)}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.modal-content{background:#111;padding:35px;border-radius:20px;width:90%;max-width:520px;box-shadow:0 0 50px rgba(255,51,102,0.6)}
.modal-content h2{text-align:center;color:#ff3366;margin-bottom:25px;font-size:1.8rem}
.modal-content input{width:100%;padding:16px;border-radius:12px;border:none;background:#222;color:white;font-size:1.1rem;margin-bottom:25px}
.modal-buttons{display:flex;gap:18px}
.modal-buttons button{flex:1;padding:16px;border:none;border-radius:12px;font-weight:bold;cursor:pointer;font-size:1.1rem}
.confirm-btn{background:linear-gradient(45deg,#ff3366,#ff5588);color:white}
.cancel-btn{background:#444;color:white}
.toast-container{position:fixed;bottom:25px;right:25px;z-index:999}
.toast{background:#111;border-left:5px solid #00ffaa;padding:16px 22px;margin-top:12px;border-radius:10px;box-shadow:0 0 20px rgba(0,0,0,0.7);min-width:280px}
.toast.danger{border-color:#ff3366}
.history-item{background:#111;padding:14px;margin:10px 0;border-radius:10px;border-left:4px solid #00ffaa;position:relative}
.history-item.disconnect{border-left-color:#ff3366}
.history-item.kick,.history-item.troll{border-left-color:#ff00aa}
.delete-history{float:right;background:transparent;color:#ff3366;border:none;cursor:pointer;font-size:18px}
</style>
</head>
<body>
<div class="container">
    <h1>ROBLOX CONTROL PANEL</h1>
    <div class="stats" id="stats">Players online: <b>0</b></div>

    <div class="tabs">
        <button class="tab-btn active" onclick="openTab('players')">Players</button>
        <button class="tab-btn" onclick="openTab('history')">History</button>
    </div>

    <div id="players" class="tab-content active">
        <div class="grid" id="playerGrid"></div>
    </div>

    <div id="history" class="tab-content">
        <div style="background:#111;padding:20px;border-radius:15px;max-width:900px;margin:auto;">
            <h2 style="text-align:center;color:#00ffaa;margin-bottom:20px">Historique des actions</h2>
            <div id="historyList"></div>
        </div>
    </div>
</div>

<!-- Modals -->
<div class="modal" id="kickModal"> ... même modal kick que avant ... </div>
<div class="modal" id="playSoundModal"> ... même modal sound ... </div>
<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId = null;
let currentSoundId = null;

const kickModal = document.getElementById("kickModal");
const playSoundModal = document.getElementById("playSoundModal");

// Toast
function toast(msg, type = "success") {
    const t = document.createElement("div");
    t.className = "toast " + (type === "danger" ? "danger" : "");
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 5000);
}

// Tabs
function openTab(tabName) {
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.getElementById(tabName).classList.add("active");
    document.querySelector(`button[onclick="openTab('${tabName}')"]`).classList.add("active");
}

// Supprimer un joueur du panel
function deletePlayer(userid) {
    if (!confirm("Supprimer ce joueur du panel ?")) return;
    fetch("/delete_player", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({userid: userid})
    });
    toast("Joueur supprimé du panel", "danger");
}

// Rendu des joueurs
function renderPlayers(data) {
    const grid = document.getElementById("playerGrid");
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
            <button class="delete-player" title="Supprimer du panel" onclick="deletePlayer('${id}')">X</button>
            <div class="status"><div class="dot ${p.online ? "online" : ""}"></div><span>${p.online ? "Online" : "Offline"}</span></div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>
            Game: <a href="https://www.roblox.com/games/${p.gameId}" target="_blank">${p.game}</a><br>JobId: ${p.jobId}</div>

            <div class="category">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588);" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:#aa00aa;" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:#00aaaa;" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:#aaaa00;" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:#55aa55;" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:#aa0000;" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:#0000aa;" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="kick-btn" style="background:orange;" onclick="openPlaySoundModal('${id}')">SOUND</button>
            </div>

            <div class="category">UNDO / MANAGE PLAYER</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','uninvisible')">VISIBLE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
            </div>
        `;
    });

    document.querySelectorAll('.card').forEach(c => {
        if (!currentIds.has(c.id.replace('card_', ''))) c.remove();
    });
}

// Rendu de l'historique
function renderHistory(history) {
    const list = document.getElementById("historyList");
    list.innerHTML = "";
    history.forEach((entry, index) => {
        const div = document.createElement("div");
        div.className = `history-item ${entry.type}`;
        let icon = "";
        if (entry.type === "connect") icon = "[Connect]";
        else if (entry.type === "disconnect") icon = "[Disconnect]";
        else if (entry.type === "kick") icon = "[Kick]";
        else if (entry.type === "troll") icon = "[Troll]";
        
        div.innerHTML = `
            <button class="delete-history" onclick="deleteHistoryItem(${index})" title="Supprimer">X</button>
            <strong>${entry.time}</strong> ${icon} 
            <strong>${entry.username}</strong> (${entry.userid}) 
            ${entry.details ? "→ " + entry.details : ""}
        `;
        list.appendChild(div);
    });
}

function deleteHistoryItem(index) {
    fetch("/delete_history_item", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({index: index})
    });
}

// Socket events
socket.on("update", data => {
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
    renderPlayers(data);
});

socket.on("history_update", renderHistory);

socket.on("kick_notice", d => toast(`${d.username} → ${d.reason}`, "danger"));
socket.on("status", d => toast(`${d.username} is now ${d.online ? "online" : "offline"}`));

// Fonctions modals et troll (inchangées, juste un peu nettoyées)
function openKickModal(id) { currentKickId = id; kickModal.classList.add("active"); document.getElementById("kickReason").focus(); }
function closeModal() { kickModal.classList.remove("active"); currentKickId = null; document.getElementById("kickReason").value = ""; }
function performKick() {
    if (!currentKickId) return;
    const reason = document.getElementById("kickReason").value.trim() || "Kicked by admin";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentKickId, reason: reason})});
    toast("Kick envoyé", "danger");
    closeModal();
}
function openPlaySoundModal(id) { currentSoundId = id; playSoundModal.classList.add("active"); document.getElementById("soundAssetId").focus(); }
function closeSoundModal() { playSoundModal.classList.remove("active"); currentSoundId = null; document.getElementById("soundAssetId").value = ""; }
function performPlaySound() {
    if (!currentSoundId) return;
    const assetId = document.getElementById("soundAssetId").value.trim();
    if (!assetId) return toast("Entre un Asset ID valide", "danger");
    sendTroll(currentSoundId, "playsound", assetId);
    closeSoundModal();
}
function sendTroll(id, cmd, assetId = null) {
    const body = {userid: id, cmd: cmd};
    if (assetId) body.assetId = assetId;
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
    toast(`${cmd.toUpperCase()} envoyé`, "danger");
}

// Événements modals
document.getElementById("cancelKick").onclick = closeModal;
document.getElementById("confirmKick").onclick = performKick;
document.getElementById("cancelSound").onclick = closeSoundModal;
document.getElementById("confirmSound").onclick = performPlaySound;
kickModal.onclick = playSoundModal.onclick = e => { if (e.target.classList.contains("modal")) e.target.classList.remove("active"); };
</script>
</body>
</html>"""

# === NOUVELLES ROUTES ===

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    if uid in connected_players:
        username = connected_players[uid]["username"]
        del connected_players[uid]
        log_action("disconnect", username, uid, "supprimé manuellement du panel")
        socketio.emit("update", {"players": connected_players, "online": sum(1 for p in connected_players.values() if p["online"]), "total": len(connected_players)})
    return jsonify({"ok": True})

@app.route("/delete_history_item", methods=["POST"])
def delete_history_item():
    check_ip()
    data = request.get_json() or {}
    index = data.get("index")
    if isinstance(index, int) and 0 <= index < len(action_history):
        removed = action_history.pop(index)
        socketio.emit("history_update", action_history)
    return jsonify({"ok": True})

# === MODIFICATIONS DANS L'API ET BROADCAST ===

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        try:
            d = request.get_json(silent=True) or {}
            uid = str(d["userid"])
            username = d.get("username", "Unknown")
            if d.get("action") == "register":
                was_offline = uid not in connected_players or not connected_players[uid]["online"]
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
                if was_offline:
                    log_action("connect", username, uid)
            elif d.get("action") == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
        except: pass
        return jsonify({"ok": True})

    # GET reste inchangé
    # ...

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    log_action("kick", name, uid, reason)
    socketio.emit("kick_notice", {"username": name, "reason": f"KICK: {reason}"})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    assetId = data.get("assetId")
    if uid and cmd:
        if assetId:
            pending_commands[uid] = {"cmd": cmd, "assetId": assetId}
        else:
            pending_commands[uid] = cmd
        name = connected_players.get(uid, {}).get("username", "Unknown")
        details = cmd if not assetId else f"{cmd} ({assetId})"
        log_action("troll", name, uid, details)
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
                if p["online"]: online += 1
                if was_online and not p["online"]:
                    log_action("disconnect", p["username"], uid, "timeout")
        for uid in to_remove:
            username = connected_players.pop(uid, {}).get("username", "Unknown")
            log_action("disconnect", username, uid, "timeout")
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
