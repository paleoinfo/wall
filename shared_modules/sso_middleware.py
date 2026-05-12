"""
Middleware SSO per le applicazioni Flask
Fornisce: validazione JWT, gestione sessioni, whitelist, rate-limiting.
"""

import jwt
import json
import os
import time
import threading
from datetime import datetime
from functools import wraps
from flask import redirect, session, render_template_string
import logging

logger = logging.getLogger(__name__)


class WhitelistManager:
    """Gestisce la whitelist degli account autorizzati."""

    def __init__(self, whitelist_path: str):
        self.whitelist_path = whitelist_path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.whitelist_path):
            default = {"enabled": False, "emails": []}
            with open(self.whitelist_path, 'w') as f:
                json.dump(default, f, indent=2)
            logger.info(f"Whitelist file creato: {self.whitelist_path} (disabled)")

    def _load(self) -> dict:
        try:
            with open(self.whitelist_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Errore lettura whitelist: {e}")
            return {"enabled": False, "emails": []}

    def is_authorized(self, email: str) -> bool:
        data = self._load()
        if not data.get("enabled", False):
            return True
        emails = [e.lower().strip() for e in data.get("emails", [])]
        return email.lower().strip() in emails

    def get_all(self) -> dict:
        return self._load()

    def add_email(self, email: str):
        with self._lock:
            data = self._load()
            normalized = email.lower().strip()
            if normalized not in data["emails"]:
                data["emails"].append(normalized)
                with open(self.whitelist_path, 'w') as f:
                    json.dump(data, f, indent=2)

    def remove_email(self, email: str):
        with self._lock:
            data = self._load()
            normalized = email.lower().strip()
            data["emails"] = [e for e in data["emails"] if e != normalized]
            with open(self.whitelist_path, 'w') as f:
                json.dump(data, f, indent=2)

    def set_enabled(self, enabled: bool):
        with self._lock:
            data = self._load()
            data["enabled"] = enabled
            with open(self.whitelist_path, 'w') as f:
                json.dump(data, f, indent=2)


class RateLimiter:
    """Rate limiting basato su sessioni attive in-memory."""

    def __init__(self,
                 max_sessions_per_user: int = 3,
                 max_sessions_global: int = 100,
                 session_ttl_seconds: int = 28800):
        self.max_sessions_per_user = max_sessions_per_user
        self.max_sessions_global = max_sessions_global
        self.session_ttl_seconds = session_ttl_seconds
        self._sessions: dict = {}
        self._lock = threading.Lock()

        logger.info(
            f"RateLimiter inizializzato: max_per_user={max_sessions_per_user}, "
            f"max_global={max_sessions_global}, ttl={session_ttl_seconds}s"
        )

    def _cleanup(self):
        now = time.time()
        expired = [
            sid for sid, data in self._sessions.items()
            if now - data["last_seen"] > self.session_ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]

    def register_session(self, session_id: str, email: str) -> tuple[bool, str]:
        with self._lock:
            self._cleanup()

            if len(self._sessions) >= self.max_sessions_global:
                return False, (
                    f"Il servizio ha raggiunto il numero massimo di sessioni attive "
                    f"({self.max_sessions_global}). Riprova tra qualche minuto."
                )

            user_sessions = [
                sid for sid, data in self._sessions.items()
                if data["email"] == email.lower()
            ]
            if len(user_sessions) >= self.max_sessions_per_user:
                return False, (
                    f"Hai raggiunto il numero massimo di sessioni simultanee "
                    f"({self.max_sessions_per_user}). Chiudi un'altra sessione e riprova."
                )

            self._sessions[session_id] = {
                "email": email.lower(),
                "created_at": time.time(),
                "last_seen": time.time()
            }
            return True, ""

    def touch_session(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["last_seen"] = time.time()

    def remove_session(self, session_id: str):
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def get_stats(self) -> dict:
        with self._lock:
            self._cleanup()
            by_user = {}
            for data in self._sessions.values():
                email = data["email"]
                by_user[email] = by_user.get(email, 0) + 1
            return {
                "total_sessions": len(self._sessions),
                "max_global": self.max_sessions_global,
                "max_per_user": self.max_sessions_per_user,
                "sessions_by_user": by_user
            }

    def is_session_valid(self, session_id: str) -> bool:
        with self._lock:
            self._cleanup()
            return session_id in self._sessions


class SSOMiddleware:
    """Middleware principale SSO."""

    def __init__(self,
                 jwt_secret: str,
                 jwt_algorithm: str = "HS256",
                 jwt_issuer: str = "sso-portal",
                 jwt_audience: str = None,
                 session_timeout: int = 28800,
                 portal_url: str = "http://localhost:5000",
                 whitelist_manager: WhitelistManager = None,
                 rate_limiter: RateLimiter = None):
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.jwt_issuer = jwt_issuer
        self.jwt_audience = jwt_audience
        self.session_timeout = session_timeout
        self.portal_url = portal_url
        self.whitelist = whitelist_manager
        self.rate_limiter = rate_limiter

    def validate_jwt(self, token: str) -> dict:
        payload = jwt.decode(
            token,
            self.jwt_secret,
            algorithms=[self.jwt_algorithm],
            issuer=self.jwt_issuer,
            audience=self.jwt_audience
        )
        logger.info(f"JWT validato per: {payload.get('email')}")
        return payload

    def create_session(self, user_data: dict, flask_session, session_id: str = None):
        import secrets
        sid = session_id or secrets.token_hex(32)

        flask_session.permanent = True
        flask_session['user'] = {
            'email': user_data.get('email'),
            'name': user_data.get('name', ''),
            'googleId': user_data.get('googleId', ''),
            'picture': user_data.get('picture', ''),
            'authenticated_at': datetime.utcnow().isoformat()
        }
        flask_session['session_id'] = sid
        logger.info(f"Sessione creata per: {user_data.get('email')}")
        return sid

    def sso_login_required(self, f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                logger.warning("Tentativo di accesso senza sessione valida")
                return redirect(self.portal_url)

            if self.rate_limiter:
                sid = session.get('session_id')
                if sid:
                    if not self.rate_limiter.is_session_valid(sid):
                        session.clear()
                        return render_sso_error(
                            "La tua sessione è scaduta. Effettua nuovamente il login.",
                            self.portal_url,
                            401
                        )
                    self.rate_limiter.touch_session(sid)

            return f(*args, **kwargs)

        return decorated_function

    def get_current_user(self, flask_session):
        return flask_session.get('user')


# ============================================
# TEMPLATE ERROR PAGE
# ============================================

ERROR_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Errore SSO</title>
    <link rel="icon" type="image/png" href="/static/favicon.png">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 100%;
            padding: 60px 40px;
            text-align: center;
        }
        .error-icon {
            font-size: 72px;
            margin-bottom: 20px;
        }
        h1 {
            color: #d32f2f;
            font-size: 28px;
            margin-bottom: 20px;
        }
        .error-message {
            color: #666;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 40px;
        }
        .btn {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 14px 32px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 16px;
            font-weight: 500;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon">🔒</div>
        <h1>Autenticazione Richiesta</h1>
        <div class="error-message">
            {{ error_message }}
        </div>
        <a href="{{ portal_url }}" class="btn">Vai al Portale SSO</a>
    </div>
</body>
</html>
"""


def render_sso_error(error_message: str, portal_url: str,
                     status_code: int = 401,
                     title: str = "Accesso Negato",
                     icon: str = "🔒"):
    """Renderizza una pagina di errore SSO"""
    return render_template_string(
        ERROR_TEMPLATE,
        error_message=error_message,
        portal_url=portal_url
    ), status_code
