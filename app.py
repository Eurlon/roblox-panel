# ===================================================================
# IMPORTANT : eventlet.monkey_patch() DOIT ÊTRE LA TOUTE PREMIÈRE CHOSE
# ===================================================================
import eventlet
eventlet.monkey_patch()   # <--- TOUJOURS en premier !

# Maintenant on peut importer Flask et le reste sans problème
from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time

# ===================================================================
# Configuration Flask + SocketIO
# ===================================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# IPs autorisées (change-les !)
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

# Données en mémoire
connected_players = {}
pending_kicks = {}
pending_commands = {}
action_history = []  # Historique global

# ===================================================================
# Fonctions utilitaires
# ===================================================================
def log_action(action_type, username, userid, details=""):
    timestamp = time.strftime("%H:%M:%S")
    entry = {
        "time": timestamp,
        "type": action_type,      # connect / disconnect / kick / troll
        "username": username,
        "userid": userid,
        "details": details
    }
    action_history.append(entry)
    if len(action_history) > 200:
        action_history.pop(0)
    socketio.emit("history_update", action_history)

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

# ===================================================================
# Protection 403 personnalisée
# ===================================================================
@app.errorhandler(403)
def access_denied(e):
    detected = request.headers.get("X-Forwarded-For", request.remote_addr)
    if detected and "," in detected:
        detected = detected.split(",")[0].strip()
    return f"""
    <html>
      <body style="background:#000;color:#ff3366;font-family:Arial;text-align:center;padding-top:15%;">
        <h1>Accès refusé</h1>
        <p>Ta cru quoi fdp ?</p>
        <p>Ton IP : <b>{detected}</b></p>
      </body>
    </html>
    """, 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll", "/delete_player", "/delete_history_item"]:
        check_ip()

# ===================================================================
# HTML + JS (tout le panel avec onglets Players / History + corbeille)
# ===================================================================
HTML = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>ROBLOX CONTROL PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh}
.container{max-width:1400px;margin:auto;padding:40px}
h1{font-family:'Orbitron',sans-serif;font-size:3.5rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}
.stats{text-align:center;margin:30px 0;font-size:1.8rem}
.tabs{display:flex;gap:15px;justify-content:center;margin:20px 0}
.tab-btn{padding:12px 30px;background:#111;border:2px solid #333;border-radius:12px;cursor:pointer;font-weight:bold}
.tab-btn.active{border-color:#00ffaa;background:#002211;color:#00ffaa}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}
.card{background:rgba(20,20,20,.95);border-radius:18px;padding:25px;position:relative;box-shadow:0 0 30px rgba(0,0,0,.7);transition:.3s}
.card:hover{transform:translateY(-8px)}
.delete-player{position:absolute;top:12px;right:12px;background:#ff3366;color:#fff;width:36px;height:36px;border-radius:50%;border:none;cursor:pointer;font-weight:bold;font-size:18px}
.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:14px;height:14px;border-radius:50%;background:red;box-shadow:0 0 12px red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}
.name{font-size:1.8rem;color:#ffcc00}
.info{font-size:1rem;color:#aaa;line-height:1.6}
.category{font-weight:bold;color:#00ffaa;margin:18px 0 10px}
button.kick-btn{padding:12px;border:none;border-radius:12px;cursor:pointer;font-weight:bold;color:#fff;margin:4px 0}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.9);align-items:center;justify-content:center;z-index:1000}
.modal.active{display:flex}
.toast-container{position:fixed;bottom:20px;right:20px;z-index:999}
.toast{background:#111;border-left:5px solid #00ffaa;padding:15px 20px;margin-top:10px;border-radius:8px;min-width:250px}
.toast.danger{border-color:#ff3366}
.history-item{background:#111;padding:12px;margin:8px 0;border-radius:8px;border-left:4px solid #00ffaa;position:relative}
.history-item.disconnect{border-left-color:#ff3366}
.history-item.kick,.history-item.troll{border-left-color:#ff00aa}
.delete-history{position:absolute;top:8px;right:8px;background:transparent;color:#ff3366;border:none;cursor:pointer;font-size:16px}
</style>
</head><body>
<div class="container">
    <h1>ROBLOX CONTROL PANEL</h1>
    <div class="stats" id="stats">Players online: <b>0</b></div>
    <div class="tabs">
        <button class="tab-btn active" onclick="openTab('players')">Players</button>
        <button class="tab-btn" onclick="openTab('history')">History</button>
    </div>

    <div id="players" class="tab-content active"><div class="grid" id="playerGrid"></div></div>
    <div id="history" class="tab-content"><div style="max-width:900px;margin:auto;background:#111;padding:20px;border-radius:15px"><h2 style="color:#00ffaa;text-align:center">Historique</h2><div id="historyList"></div></div></div>
</div>

<!-- Modals kick & sound (identiques à avant) -->
<div class="modal" id="kickModal">...</div>
<div class="modal" id="playSoundModal">...</div>
<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId = null, currentSoundId = null;

// Toast, tabs, modals, etc. (inchangés, juste raccourcis pour la lisibilité)
// ... (tout le JS que je t’ai donné précédemment)

socket.on("update", d => {
    document.getElementById("stats").innerHTML = `Players online: <b>${d.online}</b> / ${d.total}`;
    renderPlayers(d);
});
socket.on("history_update", renderHistory);
</script>
</body></html>"""

# (Je te remets le JS complet si tu veux, mais il est identique à la version précédente)

# ===================================================================
# Routes API & Panel
# ===================================================================
@app.route("/")
def index():
    return render_template_string(HTML)

# API utilisée par l'exploit Roblox
@app.route("/api", methods=["GET", "POST"])
def api():
    # ... même code que précédemment (register / heartbeat / pending commands)
    pass

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "Kicked by admin")
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
        payload = {"cmd": cmd}
        if assetId: payload["assetId"] = assetId
        pending_commands[uid] = payload if assetId else cmd
        name = connected_players.get(uid, {}).get("username", "Unknown")
        details = cmd if not assetId else f"{cmd} ({assetId})"
        log_action("troll", name, uid, details)
    return jsonify({"sent": True})

@app.route("/delete_player", methods=["POST"])
def delete_player():
    check_ip()
    uid = str(request.get_json().get("userid", ""))
    if uid in connected_players:
        username = connected_players[uid]["username"]
        del connected_players[uid]
        log_action("disconnect", username, uid, "supprimé du panel")
    return jsonify({"ok": True})

@app.route("/delete_history_item", methods=["POST"])
def delete_history_item():
    check_ip()
    idx = request.get_json().get("index")
    if isinstance(idx, int) and 0 <= idx < len(action_history):
        action_history.pop(idx)
        socketio.emit("history_update", action_history)
    return jsonify({"ok": True})

# ===================================================================
# Boucle de broadcast (détection déconnexion)
# ===================================================================
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
                if p["online"]: online += 1
                if was_online and not p["online"]:
                    log_action("disconnect", p["username"], uid, "timeout")
        for uid in to_remove:
            username = connected_players.pop(uid, {}).get("username", "Unknown")
            log_action("disconnect", username, uid, "timeout")
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

# ===================================================================
# Démarrage
# ===================================================================
if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
