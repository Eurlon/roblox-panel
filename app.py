from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}

connected_players = {}
pending_kicks = {}
pending_commands = {}
history = []

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def denied(e):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    return f"<h1>Access denied</h1><p>Your IP: {ip}</p>", 403

@app.before_request
def protect():
    if request.path in ["/", "/kick", "/troll", "/player/delete", "/history", "/history/delete"]:
        check_ip()

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ROBLOX PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
body{background:#000;color:#fff;font-family:Arial;padding:30px}
h1{color:#00ffaa}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px}
.card{background:#111;padding:20px;border-radius:15px;position:relative}
.btn{padding:8px;border:none;border-radius:8px;cursor:pointer;font-weight:bold}
.red{background:#ff3366}
.gray{background:#555}
.orange{background:orange}
.green{background:#00ffaa;color:#000}
.category{margin-top:15px;font-weight:bold;color:#00ffaa}
.trash{position:absolute;top:10px;right:15px;cursor:pointer;font-size:20px}
</style>
</head>
<body>

<h1>MANAGE PLAYER</h1>
<div class="grid" id="players"></div>

<h1 style="margin-top:60px">HISTORY</h1>
<div class="grid" id="history"></div>

<script>
const socket = io();

function deletePlayer(id){
    fetch("/player/delete",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({userid:id})
    })
}

function send(id,cmd,assetId=null){
    fetch("/troll",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({userid:id,cmd:cmd,assetId:assetId})
    })
}

function renderPlayers(data){
    const p = document.getElementById("players")
    p.innerHTML=""
    Object.entries(data.players).forEach(([id,x])=>{
        p.innerHTML+=`
        <div class="card">
            <div class="trash" onclick="deletePlayer('${id}')">🗑️</div>
            <b>${x.username}</b><br>ID ${id}<br>${x.game}
            <div class="category">MANAGE PLAYER</div>
            <button class="btn red" onclick="send('${id}','kick')">KICK</button>
            <button class="btn gray" onclick="send('${id}','freeze')">FREEZE</button>
            <button class="btn gray" onclick="send('${id}','spin')">SPIN</button>
            <button class="btn gray" onclick="send('${id}','jump')">JUMP</button>
            <button class="btn orange" onclick="send('${id}','explode')">EXPLODE</button>
        </div>`
    })
}

function loadHistory(){
    fetch("/history").then(r=>r.json()).then(h=>{
        const el=document.getElementById("history")
        el.innerHTML=""
        h.forEach((e,i)=>{
            el.innerHTML+=`
            <div class="card">
                <div class="trash" onclick="deleteHistory(${i})">🗑️</div>
                <b>${e.type.toUpperCase()}</b><br>
                ${e.username||""}<br>
                ${e.command||""} ${e.detail||""}<br>
                <small>${new Date(e.time*1000).toLocaleString()}</small>
            </div>`
        })
    })
}

function deleteHistory(i){
    fetch("/history/delete",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({index:i})
    })
}

socket.on("update",renderPlayers)
setInterval(loadHistory,3000)
</script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET","POST"])
def api():
    now = time.time()
    if request.method == "POST":
        d = request.get_json() or {}
        uid = str(d.get("userid"))
        if d.get("action") == "register":
            connected_players[uid]={
                "username":d.get("username"),
                "game":d.get("game"),
                "last":now
            }
            history.append({"type":"connect","userid":uid,"username":d.get("username"),"time":int(now)})
        elif d.get("action")=="heartbeat" and uid in connected_players:
            connected_players[uid]["last"]=now
        return jsonify(ok=True)

    uid=str(request.args.get("userid",""))
    if uid in pending_kicks:
        return jsonify({"command":"kick","reason":pending_kicks.pop(uid)})
    if uid in pending_commands:
        return jsonify({"command":pending_commands.pop(uid)})
    return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    d=request.json
    uid=str(d["userid"])
    pending_kicks[uid]=d.get("reason","Kicked")
    history.append({"type":"command","command":"kick","userid":uid,"time":int(time.time())})
    return jsonify(ok=True)

@app.route("/troll", methods=["POST"])
def troll():
    d=request.json
    uid=str(d["userid"])
    cmd=d["cmd"]
    pending_commands[uid]=cmd
    history.append({"type":"command","command":cmd,"userid":uid,"time":int(time.time())})
    return jsonify(ok=True)

@app.route("/player/delete", methods=["POST"])
def delete_player():
    uid=str(request.json.get("userid"))
    connected_players.pop(uid,None)
    return jsonify(ok=True)

@app.route("/history")
def get_history():
    return jsonify(history)

@app.route("/history/delete", methods=["POST"])
def del_history():
    i=request.json.get("index")
    if i is not None and 0<=i<len(history):
        history.pop(i)
    return jsonify(ok=True)

def loop():
    while True:
        now=time.time()
        for uid,p in list(connected_players.items()):
            if now-p["last"]>30:
                history.append({"type":"disconnect","userid":uid,"username":p["username"],"time":int(now)})
                connected_players.pop(uid)
        socketio.emit("update",{"players":connected_players})
        socketio.sleep(2)

if __name__=="__main__":
    socketio.start_background_task(loop)
    socketio.run(app,"0.0.0.0",5000)
