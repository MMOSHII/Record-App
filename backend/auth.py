"""
auth.py - Basic email/password authentication helpers.

Responsibilities:
- SQLite-backed user store (id, name, email, hashed_password)
- bcrypt password hashing via passlib
- JWT access-token creation / verification via PyJWT
- Password-reset token lifecycle (persisted in SQLite)
- Optional SMTP email sending for reset links; falls back to stdout
- Unified resolve_user_id() that accepts either a basic-auth JWT or a
  Google ID token so existing pipeline endpoints need no signature changes
"""

import os
import uuid
import sqlite3
import secrets
import smtplib
import traceback
import re
from dotenv import load_dotenv
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from typing import Optional, Dict, Any

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException

# =========================================================
# CONFIGURATION
# =========================================================
load_dotenv()
DB_PATH: str = os.getenv("AUTH_DB_PATH", "auth.db")

JWT_SECRET: str = os.getenv("JWT_SECRET")
JWT_ALGORITHM: str = "HS256"
_DEFAULT_JWT_EXPIRES_HOURS: int = 30 * 24  # 30 days
JWT_EXPIRES_HOURS: int = int(os.getenv("JWT_EXPIRES_HOURS", str(_DEFAULT_JWT_EXPIRES_HOURS)))

REFRESH_TOKEN_EXPIRES_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "90"))

# Convenience: access-token lifetime in seconds, used in API responses.
JWT_EXPIRES_SECONDS: int = JWT_EXPIRES_HOURS * 3600
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{1,28}[A-Za-z0-9])?$")
USERNAME_CHANGE_COOLDOWN_DAYS = 30

def _check_jwt_secret() -> None:
    """
    Raise a RuntimeError at startup if JWT_SECRET is unset or still the
    insecure default value.  A leaked JWT secret allows an attacker to forge
    authentication tokens for any user.
    """
    if not JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is not configured.  "
            "Set a strong random value in your .env file before starting the server.  "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )

RESET_TOKEN_EXPIRES_MINUTES: int = 60

# SMTP – all optional; if unset the reset link is printed to stdout instead
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")
SMTP_FROM: str = os.getenv("SMTP_FROM", "noreply@example.com")

# Base URL used to build the reset link sent to users
APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:5173")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# =========================================================
# DATABASE
# =========================================================

@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not exist. Call once at startup."""
    _check_jwt_secret()
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id               TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                email            TEXT NOT NULL UNIQUE,
                username         TEXT,
                username_normalized TEXT,
                username_updated_at TEXT,
                hashed_password  TEXT NOT NULL,
                created_at       TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token      TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "username" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "username_normalized" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN username_normalized TEXT")
        if "username_updated_at" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN username_updated_at TEXT")

        rows = conn.execute(
            """
            SELECT id, name, email, created_at, username, username_normalized, username_updated_at
            FROM users
            """
        ).fetchall()
        for row in rows:
            raw_username = (row["username"] or "").strip()
            normalized_username = (row["username_normalized"] or "").strip().lower()
            if raw_username and normalized_username:
                continue
            fallback_username = raw_username or row["email"].split("@")[0] or row["name"] or "user"
            unique_username = _generate_unique_username(conn, fallback_username, exclude_user_id=row["id"])
            conn.execute(
                """
                UPDATE users
                SET username = ?, username_normalized = ?, username_updated_at = ?
                WHERE id = ?
                """,
                (
                    unique_username,
                    unique_username.lower(),
                    row["username_updated_at"] or row["created_at"] or _now_iso(),
                    row["id"],
                ),
            )

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_norm_unique ON users(username_normalized)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token      TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )


# =========================================================
# USER HELPERS
# =========================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_email(email: str) -> str:
    return email.lower().strip()


def _username_seed(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_.-")
    if len(normalized) < USERNAME_MIN_LENGTH:
        normalized = "user"
    if not normalized or not normalized[0].isalnum():
        normalized = f"user_{normalized}" if normalized else "user"
    normalized = normalized[:USERNAME_MAX_LENGTH]
    while normalized and not normalized[-1].isalnum():
        normalized = normalized[:-1]
    return normalized or "user"


def validate_username(username: str) -> tuple[str, str]:
    clean = (username or "").strip()
    if not (USERNAME_MIN_LENGTH <= len(clean) <= USERNAME_MAX_LENGTH):
        raise HTTPException(
            status_code=400,
            detail=f"Username must be {USERNAME_MIN_LENGTH}-{USERNAME_MAX_LENGTH} characters.",
        )
    if not USERNAME_REGEX.fullmatch(clean):
        raise HTTPException(
            status_code=400,
            detail="Username may only contain letters, numbers, dots, underscores, and hyphens, and must start/end with a letter or number.",
        )
    return clean, clean.lower()


def _username_exists(conn: sqlite3.Connection, normalized_username: str, exclude_user_id: Optional[str] = None) -> bool:
    if exclude_user_id:
        row = conn.execute(
            "SELECT 1 FROM users WHERE username_normalized = ? AND id != ? LIMIT 1",
            (normalized_username, exclude_user_id),
        ).fetchone()
        return row is not None
    row = conn.execute(
        "SELECT 1 FROM users WHERE username_normalized = ? LIMIT 1",
        (normalized_username,),
    ).fetchone()
    return row is not None


def _generate_unique_username(conn: sqlite3.Connection, seed_value: str, exclude_user_id: Optional[str] = None) -> str:
    base = _username_seed(seed_value)
    candidate = base
    suffix = 1
    while _username_exists(conn, candidate.lower(), exclude_user_id=exclude_user_id):
        suffix_text = str(suffix)
        trimmed = base[: max(USERNAME_MIN_LENGTH, USERNAME_MAX_LENGTH - len(suffix_text) - 1)]
        candidate = f"{trimmed}_{suffix_text}"
        suffix += 1
    return candidate


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, email, username, username_normalized, username_updated_at, hashed_password
            FROM users
            WHERE email = ?
            """,
            (_normalize_email(email),),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, email, username, username_updated_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    normalized = (username or "").strip().lower()
    if not normalized:
        return None
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, email, username, username_normalized, username_updated_at, hashed_password
            FROM users
            WHERE username_normalized = ?
            """,
            (normalized,),
        ).fetchone()
    return dict(row) if row else None


def create_user(name: str, email: str, password: str, username: Optional[str] = None) -> Dict[str, Any]:
    """
    Register a new user.  Raises HTTPException 409 if email already exists.
    Returns the new user dict (without hashed_password).
    """
    email = _normalize_email(email)
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user_id = f"basic_{uuid.uuid4().hex}"
    hashed = pwd_context.hash(password)
    now_iso = _now_iso()
    with _get_conn() as conn:
        if username and username.strip():
            clean_username, normalized_username = validate_username(username)
            if _username_exists(conn, normalized_username):
                raise HTTPException(status_code=409, detail="Username is already taken.")
        else:
            clean_username = _generate_unique_username(conn, email.split("@")[0] or name)
            normalized_username = clean_username.lower()
        conn.execute(
            """
            INSERT INTO users (
                id, name, email, username, username_normalized, username_updated_at, hashed_password, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, name.strip(), email, clean_username, normalized_username, now_iso, hashed, now_iso),
        )
    return {"id": user_id, "name": name.strip(), "email": email, "username": clean_username}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def update_password(user_id: str, new_password: str) -> None:
    hashed = pwd_context.hash(new_password)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET hashed_password = ? WHERE id = ?",
            (hashed, user_id),
        )


def authenticate_basic_user(identifier: str, password: str) -> Dict[str, Any]:
    clean_identifier = (identifier or "").strip()
    if not clean_identifier:
        raise HTTPException(status_code=401, detail="Incorrect email/username or password.")
    user = (
        get_user_by_email(clean_identifier)
        if "@" in clean_identifier
        else get_user_by_username(clean_identifier)
    )
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email/username or password.")
    return user


def update_basic_profile(
    user_id: str,
    *,
    email: Optional[str] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, email, username, username_normalized, username_updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")

        current = dict(row)
        next_email = current["email"]
        if email is not None:
            candidate_email = _normalize_email(email)
            if not candidate_email:
                raise HTTPException(status_code=400, detail="Email is required.")
            if candidate_email != current["email"]:
                existing_email_user = conn.execute(
                    "SELECT id FROM users WHERE email = ?",
                    (candidate_email,),
                ).fetchone()
                if existing_email_user and existing_email_user["id"] != user_id:
                    raise HTTPException(status_code=409, detail="An account with this email already exists.")
                next_email = candidate_email

        next_username = current["username"]
        next_username_normalized = current["username_normalized"]
        next_username_updated_at = current["username_updated_at"]

        if username is not None:
            clean_username, normalized_username = validate_username(username)
            if normalized_username != current["username_normalized"]:
                last_updated_at = current.get("username_updated_at")
                if last_updated_at:
                    try:
                        previous_update = datetime.fromisoformat(last_updated_at.replace("Z", "+00:00"))
                    except ValueError:
                        previous_update = datetime.now(timezone.utc) - timedelta(days=USERNAME_CHANGE_COOLDOWN_DAYS + 1)
                    cooldown_end = previous_update + timedelta(days=USERNAME_CHANGE_COOLDOWN_DAYS)
                    if datetime.now(timezone.utc) < cooldown_end:
                        remaining_days = max(1, int((cooldown_end - datetime.now(timezone.utc)).days + 1))
                        raise HTTPException(
                            status_code=429,
                            detail=f"Username can only be changed every {USERNAME_CHANGE_COOLDOWN_DAYS} days. Try again in {remaining_days} day(s).",
                        )
                if _username_exists(conn, normalized_username, exclude_user_id=user_id):
                    raise HTTPException(status_code=409, detail="Username is already taken.")
                next_username = clean_username
                next_username_normalized = normalized_username
                next_username_updated_at = _now_iso()

        conn.execute(
            """
            UPDATE users
            SET email = ?, username = ?, username_normalized = ?, username_updated_at = ?
            WHERE id = ?
            """,
            (next_email, next_username, next_username_normalized, next_username_updated_at, user_id),
        )

    return {
        "id": user_id,
        "name": current["name"],
        "email": next_email,
        "username": next_username,
        "username_updated_at": next_username_updated_at,
    }


# =========================================================
# JWT ACCESS TOKENS
# =========================================================

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "basic",
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRES_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_basic_token(token: str) -> str:
    """
    Decode and validate a basic-auth JWT.
    Returns the user_id (sub).  Raises HTTPException 401 on failure.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "basic":
            raise ValueError("Not a basic-auth token.")
        user_id: str = payload["sub"]
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")


# =========================================================
# REFRESH TOKENS
# =========================================================

def create_refresh_token(user_id: str) -> str:
    """
    Generate a long-lived refresh token and persist it.
    Each user may have many refresh tokens (one per device/session).
    Returns the token string.
    """
    token = secrets.token_urlsafe(48)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRES_DAYS)
    ).timestamp()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO refresh_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def rotate_refresh_token(old_token: str) -> tuple[str, str]:
    """
    Validate a refresh token, delete it (one-time use), and issue a new pair.
    Returns (new_access_token, new_refresh_token).
    Raises HTTPException 401 if invalid or expired.
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM refresh_tokens WHERE token = ?",
            (old_token,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or already used refresh token.")
        if datetime.now(timezone.utc).timestamp() > row["expires_at"]:
            conn.execute("DELETE FROM refresh_tokens WHERE token = ?", (old_token,))
            raise HTTPException(status_code=401, detail="Refresh token expired. Please sign in again.")
        user_id: str = row["user_id"]
        conn.execute("DELETE FROM refresh_tokens WHERE token = ?", (old_token,))

    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    return new_access, new_refresh


# =========================================================
# PASSWORD RESET TOKENS
# =========================================================

def create_reset_token(user_id: str) -> str:
    """
    Generate a secure password-reset token and persist it.

    32 bytes of cryptographic randomness gives 256 bits of entropy,
    which is well above the NIST recommendation for single-use tokens
    (at least 20 bytes / 112 bits of entropy).
    """
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRES_MINUTES)
    ).timestamp()
    with _get_conn() as conn:
        # Remove any previous tokens for this user
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO password_reset_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def consume_reset_token(token: str) -> str:
    """
    Validate the reset token and return the associated user_id.
    Deletes the token so it cannot be reused.
    Raises HTTPException 400 if invalid or expired.
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM password_reset_tokens WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or already used password reset link.")
        if datetime.now(timezone.utc).timestamp() > row["expires_at"]:
            conn.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
            raise HTTPException(status_code=400, detail="Password reset link has expired. Please request a new one.")
        user_id = row["user_id"]
        conn.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
    return user_id


# =========================================================
# EMAIL
# =========================================================

def send_reset_email(email: str, reset_token: str) -> None:
    """
    Send a password-reset email.  If SMTP is not configured, print the link
    to stdout so developers can test without an email server.
    """
    reset_url = f"{APP_BASE_URL}/reset-password?token={reset_token}"

    if not SMTP_HOST:
        # Development fallback: print link to console
        print(
            f"\n[AUTH] Password reset requested for {email}\n"
            f"[AUTH] Reset URL: {reset_url}\n"
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Reset your Audio Intelligence password"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Hello,\n\n"
        f"You requested a password reset for your Audio Intelligence account.\n\n"
        f"Click the link below to set a new password (valid for {RESET_TOKEN_EXPIRES_MINUTES} minutes):\n\n"
        f"{reset_url}\n\n"
        f"If you did not request this, you can safely ignore this email.\n"
    )
    msg.add_alternative(
        f"""
        <p>Hello,</p>
        <p>You requested a password reset for your Audio Intelligence account.</p>
        <p><a href="{reset_url}">Reset my password</a></p>
        <p>This link expires in {RESET_TOKEN_EXPIRES_MINUTES} minutes.</p>
        <p>If you did not request this, you can safely ignore this email.</p>
        """,
        subtype="html",
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    except Exception:
        traceback.print_exc()
        # Do not expose SMTP errors to the client
        print(f"[AUTH] WARNING: could not send reset email to {email}. Reset URL: {reset_url}")


# =========================================================
# UNIFIED AUTH
# =========================================================

def resolve_user_id(token: str, google_client_id: Optional[str] = None) -> str:
    """
    Accept either a basic-auth JWT or a Google ID token.

    Tries the cheap local JWT verification first.  If that fails (wrong type,
    bad signature, etc.) it falls back to Google OAuth verification.

    Pass google_client_id to enable the Google fallback; if None the fallback
    is skipped and an HTTPException 401 is raised for non-basic tokens.
    """
    # Fast path: basic-auth JWT
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") == "basic":
            return payload["sub"]
    except Exception:
        pass

    # Slow path: Google ID token
    if google_client_id:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        try:
            idinfo = google_id_token.verify_oauth2_token(
                token, google_requests.Request(), google_client_id
            )
            return idinfo["sub"]
        except Exception:
            pass

    raise HTTPException(
        status_code=401,
        detail="Invalid or expired authentication token.",
    )
