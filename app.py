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
history_log = []

def add_history(event, username="Unknown", userid=None, extra=None):
    history_log.append({
        "time": time.strftime("%H:%M:%S"),
        "event": event,
        "username": username,
        "userid": userid,
        "extra": extra
    })

def check_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    if ip not in ALLOWED_IPS:
        abort(403)

@app.errorhandler(403)
def denied(e):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    return f"<h1 style='color:red;text-align:center'>ACCESS DENIED<br>{ip}</h1>",403

@app.before_request
def protect():
    if request.path in ["/","/kick","/troll","/history","/player/delete"]:
        check_ip()

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ROBLOX CONTROL PANEL</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#fff;font-family:Inter}
.container{max-width:1200px;margin:auto;padding:40px}
h1{font-family:Orbitron;color:#00ffaa;text-align:center;font-size:3.5rem}
.stats{text-align:center;margin:25px;font-size:1.6rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:25px}

.card{
background:#111;border-radius:18px;padding:25px;
box-shadow:0 0 30px rgba(0,0,0,.7);
position:relative;
animation:fade .4s ease
}
@keyframes fade{from{opacity:0;transform:translateY(10px)}to{opacity:1}}

.trash{
position:absolute;top:15px;right:15px;
cursor:pointer;font-size:18px;opacity:.6
}
.trash:hover{opacity:1;transform:scale(1.2)}

.status{display:flex;gap:10px;margin-bottom:12px}
.dot{width:14px;height:14px;border-radius:50%;background:red}
.dot.online{background:#00ffaa}

.name{color:#ffcc00;font-size:1.7rem;margin-bottom:10px}
.info{color:#aaa;margin-bottom:15px}

.category{
color:#00ffaa;
margin:15px 0 8px;
font-weight:bold;
animation:slide .3s ease
}
@keyframes slide{from{opacity:0;transform:translateX(-10px)}to{opacity:1}}

button{
border:none;border-radius:12px;
padding:12px;font-weight:bold;
cursor:pointer;color:white;
transition:.2s
}
button:hover{transform:scale(1.05)}

.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);align-items:center;justify-content:center}
.modal.active{display:flex}
.modal-content{background:#111;padding:25px;border-radius:20px;width:90%;max-width:520px}

.toast-container{position:fixed;bottom:20px;right:20px}
.toast{background:#111;border-left:5px solid #00ffaa;padding:12px;margin-top:10px}
.toast.danger{border-color:#ff3366}
</style>
</head>

<body>
<div class="container">
<h1>ROBLOX CONTROL PANEL</h1>
<div class="stats" id="stats"></div>
<div class="grid" id="players"></div>
</div>

<div class="modal" id="historyModal">
<div class="modal-content">
<h2 style="color:#00ffaa">History</h2>
<div id="historyList" style="max-height:400px;overflow:auto;margin-top:10px"></div>
<button style="background:#444;margin-top:10px" onclick="closeHistory()">Close</button>
</div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();

function toast(msg,type="success"){
let t=document.createElement("div");
t.className="toast "+(type=="danger"?"danger":"");
t.textContent=msg;
toasts.appendChild(t);
setTimeout(()=>t.remove(),4000);
}

function deletePlayer(id){
fetch("/player/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id})});
toast("Player removed","danger");
}

function openHistory(){
fetch("/history").then(r=>r.json()).then(d=>{
historyList.innerHTML="";
d.forEach((h,i)=>{
historyList.innerHTML+=`
<div style="border-bottom:1px solid #333;padding:6px">
[${h.time}] ${h.event.toUpperCase()} - ${h.username}
<span style="float:right;cursor:pointer" onclick="deleteHistory(${i})">🗑️</span>
</div>`;
});
historyModal.classList.add("active");
});
}
function closeHistory(){historyModal.classList.remove("active")}
function deleteHistory(id){fetch("/history?id="+id,{method:"DELETE"});openHistory()}

function sendTroll(id,cmd){
fetch("/troll",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id,cmd:cmd})});
toast(cmd+" sent","danger");
}

socket.on("update",data=>{
stats.innerHTML=`Players online: <b>${data.online}</b> / ${data.total}`;
players.innerHTML="";
Object.entries(data.players).forEach(([id,p])=>{
players.innerHTML+=`
<div class="card">
<div class="trash" onclick="deletePlayer('${id}')">🗑️</div>
<div class="status"><div class="dot ${p.online?"online":""}"></div>${p.online?"Online":"Offline"}</div>
<div class="name">${p.username} (${id})</div>
<div class="info">${p.executor}<br>${p.game}</div>

<div class="category">MANAGE PLAYER</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
<button style="background:#ff3366" onclick="sendTroll('${id}','kick')">KICK</button>
<button style="background:#666" onclick="sendTroll('${id}','freeze')">FREEZE</button>
</div>

<div class="category">HISTORY</div>
<button style="background:#222" onclick="openHistory()">OPEN HISTORY</button>
</div>`;
});
});
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET","POST"])
def api():
    now=time.time()
    if request.method=="POST":
        d=request.get_json() or {}
        uid=str(d.get("userid",""))
        if d.get("action")=="register":
            connected_players[uid]={
                "username":d.get("username"),
                "executor":d.get("executor"),
                "game":d.get("game"),
                "last":now,
                "online":True
            }
            add_history("connect",d.get("username"),uid)
        elif d.get("action")=="heartbeat" and uid in connected_players:
            connected_players[uid]["last"]=now
        return jsonify({"ok":True})

    uid=str(request.args.get("userid",""))
    if uid in pending_commands:
        return jsonify({"command":pending_commands.pop(uid)})
    if uid in pending_kicks:
        return jsonify({"command":"kick","reason":pending_kicks.pop(uid)})
    return jsonify({})

@app.route("/troll", methods=["POST"])
def troll():
    d=request.get_json() or {}
    uid=str(d.get("userid"))
    cmd=d.get("cmd")
    if uid and cmd:
        pending_commands[uid]=cmd
        add_history("command",connected_players.get(uid,{}).get("username"),uid,cmd)
    return jsonify({"ok":True})

@app.route("/history", methods=["GET","DELETE"])
def history():
    if request.method=="GET":
        return jsonify(history_log)
    idx=request.args.get("id")
    if idx:
        try: history_log.pop(int(idx))
        except: pass
    return jsonify({"ok":True})

@app.route("/player/delete", methods=["POST"])
def delete_player():
    uid=str((request.get_json() or {}).get("userid"))
    if uid in connected_players:
        add_history("purge",connected_players[uid]["username"],uid)
        connected_players.pop(uid)
    return jsonify({"ok":True})

def broadcast():
    while True:
        now=time.time()
        online=0
        for p in connected_players.values():
            p["online"]=now-p["last"]<15
            if p["online"]: online+=1
        socketio.emit("update",{"players":connected_players,"online":online,"total":len(connected_players)})
        socketio.sleep(2)

if __name__=="__main__":
    socketio.start_background_task(broadcast)
    socketio.run(app,host="0.0.0.0",port=5000)
