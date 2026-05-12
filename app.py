"""
WALL - Image Mosaic Gallery - Con integrazione SSO
Versione adattata per funzionare con il portale SSO centralizzato
"""

import os
import sys
import random
import secrets
from datetime import timedelta
from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()

# Importa il middleware SSO
try:
    from shared_modules.sso_middleware import SSOMiddleware, WhitelistManager, RateLimiter, render_sso_error
except ImportError:
    # Fallback se non è un package
    from sso_middleware import SSOMiddleware, WhitelistManager, RateLimiter, render_sso_error

app = Flask(__name__)
# Configura ProxyFix per leggere gli header da Nginx
# x_for=1, x_proto=1, x_host=1, x_port=1 (dipende dai parametri proxy_set_header)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# ============================================
# CONFIGURAZIONE
# ============================================

# Secret key per le sessioni Flask (da variabile d'ambiente)
app.secret_key = os.getenv('SERVER_SECRET_KEY', 'dev-secret-change-in-production')
app.permanent_session_lifetime = timedelta(hours=8)

# Configurazione cartella dati utenti
# Mantieni la struttura esistente: users_data/username/
SERVER_FOLDER = os.path.join(os.path.dirname(__file__), 'users_data')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# ============================================
# CONFIGURAZIONE SSO
# ============================================

# Modalità SSO: 'dev' o 'production'
SSO_MODE = os.getenv('SSO_MODE', 'production').lower()
DEV_USER_EMAIL = os.getenv('DEV_USER_EMAIL', 'demo@example.com')

# IMPORTANTE: Questi parametri DEVONO corrispondere a quelli configurati
# nel portale SSO per questa specifica applicazione (WALL)

SSO_CONFIG = {
    'jwt_secret': os.getenv('JWT_SECRET'),
    'jwt_algorithm': 'HS256',
    'jwt_issuer': 'sso-portal',
    'jwt_audience': os.getenv('APP_AUDIENCE', 'wall-app'),
    'session_timeout': 28800,  # 8 ore
    'portal_url': os.getenv('PORTAL_URL', 'http://localhost:5000')
}

# Verifica che JWT_SECRET sia configurato (solo in modalità production)
if SSO_MODE == 'production' and not SSO_CONFIG['jwt_secret']:
    raise ValueError("JWT_SECRET non configurato! In modalità production serve JWT_SECRET nel file .env")

if SSO_MODE == 'production':
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )


DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

whitelist_manager = WhitelistManager(
    whitelist_path=os.path.join(DATA_DIR, 'whitelist.json')
)

rate_limiter = RateLimiter(
    max_sessions_per_user=int(os.getenv('MAX_SESSIONS_PER_USER', 3)),
    max_sessions_global=int(os.getenv('MAX_SESSIONS_GLOBAL', 100)),
    session_ttl_seconds=28800
)



# Inizializza il middleware SSO
sso_middleware = SSOMiddleware(
    **SSO_CONFIG,
    whitelist_manager=whitelist_manager,
    rate_limiter=rate_limiter
)


# ============================================
# UTILITY FUNCTIONS
# ============================================

def ensure_server_folder():
    """Crea la cartella server se non esiste"""
    if not os.path.exists(SERVER_FOLDER):
        os.makedirs(SERVER_FOLDER)


def ensure_user_folder(username: str):
    """Crea la cartella specifica per l'utente se non esiste"""
    user_path = os.path.join(SERVER_FOLDER, username)
    if not os.path.exists(user_path):
        os.makedirs(user_path)


def get_username(email: str) -> str:
    """Estrae lo username dall'indirizzo email"""
    return email.split('@')[0]


def get_user_images(username: str) -> list:
    """
    Ottiene la lista delle immagini per un utente
    
    Args:
        username: Nome utente
    
    Returns:
        Lista di nomi file immagine
    """
    user_path = os.path.join(SERVER_FOLDER, username)
    
    if not os.path.exists(user_path) or not os.path.isdir(user_path):
        return []
    
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    images = []
    
    for f in os.listdir(user_path):
        if os.path.splitext(f)[1].lower() in allowed_extensions:
            images.append(f)
    
    # Mischia le immagini per ordine casuale
    random.shuffle(images)
    
    return images


def get_user_settings(username: str) -> dict:
    """Carica le impostazioni dell'utente dal file JSON locale"""
    settings_path = os.path.join(SERVER_FOLDER, username, 'settings.json')
    defaults = {
        'gallery_bg_color': '#f5f7fa',
        'gallery_thumb_size': '250'
    }
    
    if os.path.exists(settings_path):
        try:
            import json
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                return {**defaults, **settings}
        except Exception as e:
            app.logger.error(f"Errore caricamento settings per {username}: {e}")
    
    return defaults


def save_user_settings(username: str, settings: dict):
    """Salva le impostazioni dell'utente su file JSON locale"""
    ensure_user_folder(username)
    settings_path = os.path.join(SERVER_FOLDER, username, 'settings.json')
    try:
        import json
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        app.logger.error(f"Errore salvataggio settings per {username}: {e}")


# ============================================
# ROUTE SSO
# ============================================

@app.route('/sso/login')
def sso_login():
    """
    Endpoint SSO - riceve il JWT dal portale, lo valida e crea la sessione
    
    Query params:
        token: JWT firmato dal portale SSO
    """
    token = request.args.get('token')
    
    # In modalità dev, permettiamo di simulare il login tramite query parameter
    if SSO_MODE == 'dev' and not token:
        dev_email = request.args.get('username') or request.args.get('email') or DEV_USER_EMAIL
        app.logger.info(f"🔧 DEV MODE: Simulazione login SSO per {dev_email}")
        
        user_data = {
            'email': dev_email,
            'name': dev_email.split('@')[0].replace('.', ' ').title(),
            'googleId': 'dev-user-id',
            'picture': ''
        }
        return _complete_login(user_data)

    if not token:
        return render_sso_error(
            "Token SSO mancante. Accedi tramite il portale SSO.",
            SSO_CONFIG['portal_url']
        )
    
    try:
        # Valida il JWT
        user_data = sso_middleware.validate_jwt(token)
        return _complete_login(user_data)
        
    except Exception as e:
        app.logger.error(f"Errore validazione SSO: {e}")
        return render_sso_error(
            f"Token SSO invalido o scaduto: {str(e)}",
            SSO_CONFIG['portal_url']
        )


def _complete_login(user_data: dict):
    """Flusso post-validazione: whitelist, rate-limit, sessione e redirect."""
    email = user_data.get('email', '')

    if not whitelist_manager.is_authorized(email):
        app.logger.warning(f"Accesso negato da whitelist: {email}")
        return render_sso_error(
            f"Il tuo account ({email}) non è autorizzato ad accedere a questa applicazione. "
            "Contatta l'amministratore se ritieni sia un errore.",
            SSO_CONFIG['portal_url'],
            status_code=403,
            title="Account Non Autorizzato",
            icon="🚫"
        )

    session_id = secrets.token_hex(32)
    allowed, reason = rate_limiter.register_session(session_id, email)
    if not allowed:
        app.logger.warning(f"Rate limit raggiunto per: {email}")
        return render_sso_error(
            reason,
            SSO_CONFIG['portal_url'],
            status_code=429,
            title="Troppe Sessioni Attive",
            icon="⏱️"
        )

    sso_middleware.create_session(user_data, session, session_id=session_id)
    ensure_user_folder(get_username(email))
    return redirect(url_for('gallery', _external=True))


@app.route('/logout')
def logout():
    """Logout - rimuove la sessione e redirect al portale"""
    sid = session.get('session_id')
    if sid:
        rate_limiter.remove_session(sid)
    session.clear()
    return redirect(SSO_CONFIG['portal_url'])


# ============================================
# ROUTE APPLICAZIONE
# ============================================

@app.route('/')
def index():
    """
    Homepage - se l'utente è autenticato mostra la gallery,
    altrimenti comportamento basato su SSO_MODE
    """
    if 'user' in session:
        return redirect(url_for('gallery', _external=True))
    
    # Modalità sviluppo: auto-login con utente di test
    if SSO_MODE == 'dev':
        # Supporta username dinamico via query string
        user_param = request.args.get('username') or request.args.get('email')
        current_dev_user = user_param if user_param else DEV_USER_EMAIL
        
        app.logger.info(f"🔧 MODALITÀ DEV: Auto-login come {current_dev_user}")
        session.permanent = True
        session['user'] = {
            'email': current_dev_user,
            'name': current_dev_user.split('@')[0].replace('.', ' ').title(),
            'googleId': 'dev-user-id',
            'picture': '',
            'authenticated_at': 'dev-mode'
        }
        
        # Assicurati che la cartella utente esista in modalità dev
        ensure_user_folder(get_username(current_dev_user))
        
        return redirect(url_for('gallery', _external=True))
    
    # Modalità production: redirect al portale SSO
    return render_sso_error(
        "Accedi tramite il portale SSO per visualizzare la tua galleria di immagini.",
        SSO_CONFIG['portal_url']
    )


@app.route('/gallery')
@sso_middleware.sso_login_required
def gallery():
    """Mostra la galleria di immagini dell'utente autenticato"""
    user = session['user']
    email = user['email']
    
    # Estrai username dall'email (parte prima della @)
    username = get_username(email)
    
    # Assicurati che la cartella esista (se cancellata manualmente)
    ensure_user_folder(username)
    
    # Carica settings da file (persistente)
    user_settings = get_user_settings(username)
    
    # Ottieni le immagini dell'utente
    images = get_user_images(username)
    
    return render_template(
        'gallery.html',
        user=user,
        username=username,
        images=images,
        portal_url=SSO_CONFIG['portal_url'],
        bg_color=user_settings['gallery_bg_color'],
        thumb_size=user_settings['gallery_thumb_size']
    )


@app.route('/settings', methods=['GET', 'POST'])
@sso_middleware.sso_login_required
def settings():
    """Pagina delle impostazioni dell'utente"""
    user = session['user']
    username = get_username(user['email'])
    
    if request.method == 'POST':
        # Nuovi settings dal form
        new_settings = {
            'gallery_bg_color': request.form.get('bg_color', '#f5f7fa'),
            'gallery_thumb_size': request.form.get('thumb_size', '250')
        }
        # Salva su file JSON (permanente)
        save_user_settings(username, new_settings)
        
        return redirect(url_for('settings', success='Impostazioni salvate con successo'))
    
    # Carica settings correnti
    user_settings = get_user_settings(username)
    
    return render_template(
        'settings.html',
        user=user,
        bg_color=user_settings['gallery_bg_color'],
        thumb_size=user_settings['gallery_thumb_size'],
        portal_url=SSO_CONFIG['portal_url']
    )


@app.route('/upload', methods=['POST'])
@sso_middleware.sso_login_required
def upload_image():
    """Gestisce l'upload di nuove immagini"""
    if 'image' not in request.files:
        return redirect(url_for('gallery'))
    
    file = request.files['image']
    if file.filename == '':
        return redirect(url_for('gallery'))
    
    user = session['user']
    username = get_username(user['email'])
    
    # Assicurati che la cartella dell'utente esista
    ensure_user_folder(username)
    
    user_path = os.path.join(SERVER_FOLDER, username)
    
    if file:
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext in ALLOWED_EXTENSIONS:
            filename = secure_filename(file.filename)
            # Se il file esiste già, aggiungi un prefisso casuale
            if os.path.exists(os.path.join(user_path, filename)):
                filename = f"{random.randint(1000, 9999)}_{filename}"
            
            file.save(os.path.join(user_path, filename))
            
    return redirect(url_for('gallery'))


@app.route('/delete/<filename>', methods=['POST'])
@sso_middleware.sso_login_required
def delete_image(filename):
    """Cancella un'immagine specifica"""
    user = session['user']
    username = get_username(user['email'])
    
    # Sicurezza: impedisci path traversal
    filename = os.path.basename(filename)
    file_path = os.path.join(SERVER_FOLDER, username, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    return redirect(url_for('gallery'))


@app.route('/image/<username>/<filename>')
@sso_middleware.sso_login_required
def serve_image(username, filename):
    """
    Serve le immagini in modo sicuro
    Verifica che l'utente possa accedere solo alle proprie immagini
    """
    user = session['user']
    email = user['email']
    current_username = get_username(email)
    
    # Sicurezza: l'utente può accedere solo alle proprie immagini
    if username != current_username:
        return "Accesso negato", 403
    
    user_path = os.path.join(SERVER_FOLDER, username)
    return send_from_directory(user_path, filename)


# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(e):
    return render_sso_error("Pagina non trovata", SSO_CONFIG['portal_url'], 404)


@app.errorhandler(403)
def forbidden(e):
    return render_sso_error("Accesso negato", SSO_CONFIG['portal_url'], 403)


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    ensure_server_folder()
    
    app.logger.info(f"Image Mosaic Gallery avviato")
    app.logger.info(f"Modalità SSO: {SSO_MODE.upper()}")
    if SSO_MODE == 'dev':
        app.logger.info(f"🔧 DEV MODE: Auto-login come {DEV_USER_EMAIL}")
        app.logger.info(f"   Per cambiare utente, modifica DEV_USER_EMAIL nel file .env")
    else:
        app.logger.info(f"Portale SSO: {SSO_CONFIG['portal_url']}")
    app.logger.info(f"Cartella utenti: {SERVER_FOLDER}")
    app.logger.info(f"Audience JWT: {SSO_CONFIG['jwt_audience']}")
    app.logger.info(
        f"Rate limit: max {rate_limiter.max_sessions_per_user} sessioni/utente, "
        f"max {rate_limiter.max_sessions_global} sessioni globali"
    )
    
    # Permetti il binding dell'host via variabile d'ambiente (utile per Docker)
    bind_host = os.getenv('FLASK_HOST', '127.0.0.1')
    bind_port = int(os.getenv('FLASK_PORT', '3020'))
    
    app.run(
        host=bind_host,
        port=bind_port,
        debug=os.getenv('DEBUG', 'False').lower() == 'true'
    )
