"""
auth.py – SQLite-backed authentication module.

Supports:
  - Email / password accounts (bcrypt + PyJWT)
  - Google OAuth ID token verification
  - Password-reset tokens (one-time use, expiring)

All functions that map to HTTP-layer errors raise fastapi.HTTPException
directly so that the FastAPI route handlers do not need extra try/except
wrappers for expected failure cases.
"""

import datetime
import os
import secrets
import sqlite3
import uuid
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import HTTPException

# =========================================================
# CONFIGURATION
# =========================================================

DB_PATH: str = os.getenv("DB_PATH", "auth.db")
_JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
_JWT_ALGORITHM: str = "HS256"
_JWT_EXPIRY_HOURS: int = 24 * 7          # 7 days
_RESET_TOKEN_EXPIRY_MINUTES: int = 60    # 1 hour


# =========================================================
# DATABASE HELPERS
# =========================================================

def init_db() -> None:
    """
    Initialise the SQLite database and create tables if they do not exist.
    Raises RuntimeError when JWT_SECRET has not been changed from the default
    so that the server refuses to start in an insecure configuration.
    """
    if _JWT_SECRET == "change-me-in-production":
        raise RuntimeError(
            "JWT_SECRET must be set to a cryptographically-random value "
            "in the environment (never use the default)."
        )

    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            email        TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reset_tokens (
            token       TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            used        INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# USER MANAGEMENT
# =========================================================

def create_user(name: str, email: str, password: str) -> Dict[str, Any]:
    """
    Create a new user account.
    Raises HTTPException 409 if the email is already registered.
    """
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO users (id, name, email, hashed_password, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, name, email, hashed, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered.")
    finally:
        conn.close()

    return {"id": user_id, "name": name, "email": email}


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Return the user row for *email*, or None if not found."""
    conn = _connect()
    row = conn.execute(
        "SELECT id, name, email, hashed_password FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Return id/name/email for *user_id*, or None if not found."""
    conn = _connect()
    row = conn.execute(
        "SELECT id, name, email FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_password(user_id: str, new_password: str) -> None:
    """Replace the stored password hash for *user_id*."""
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = _connect()
    conn.execute(
        "UPDATE users SET hashed_password = ? WHERE id = ?",
        (hashed, user_id),
    )
    conn.commit()
    conn.close()


# =========================================================
# PASSWORD HELPERS
# =========================================================

def verify_password(plain: str, hashed: str) -> bool:
    """Return True when *plain* matches the bcrypt *hashed* value."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# =========================================================
# JWT – ACCESS TOKENS
# =========================================================

def create_access_token(user_id: str) -> str:
    """Issue a signed JWT access token for *user_id*."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + datetime.timedelta(hours=_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_basic_token(token: str) -> str:
    """
    Validate a basic-auth JWT and return the embedded user_id (sub).
    Raises HTTPException 401 for any invalid/expired token.
    """
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token has no subject.")

    return user_id


# =========================================================
# PASSWORD RESET TOKENS
# =========================================================

def create_reset_token(user_id: str) -> str:
    """Generate a one-time password-reset token, persisted to the DB."""
    token = secrets.token_urlsafe(32)
    expires_at = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=_RESET_TOKEN_EXPIRY_MINUTES)
    ).isoformat()

    conn = _connect()
    conn.execute(
        "INSERT INTO reset_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    conn.commit()
    conn.close()
    return token


def consume_reset_token(token: str) -> str:
    """
    Validate and consume a password-reset token.
    Returns the associated user_id on success.
    Raises HTTPException 400 for invalid / expired / already-used tokens.
    """
    conn = _connect()
    row = conn.execute(
        "SELECT user_id, expires_at, used FROM reset_tokens WHERE token = ?",
        (token,),
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user_id, expires_at, used = row["user_id"], row["expires_at"], row["used"]

    if used:
        conn.close()
        raise HTTPException(status_code=400, detail="Reset token has already been used.")

    expiry_dt = datetime.datetime.fromisoformat(expires_at).replace(
        tzinfo=datetime.timezone.utc
    )
    if expiry_dt < datetime.datetime.now(datetime.timezone.utc):
        conn.close()
        raise HTTPException(status_code=400, detail="Reset token has expired.")

    conn.execute("UPDATE reset_tokens SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return user_id


def send_reset_email(email: str, reset_token: str) -> None:
    """
    Send a password-reset email.

    The default implementation prints the reset link to server logs so that
    self-hosted users can retrieve it without configuring an email provider.
    Replace (or extend) this function to integrate a real delivery service
    (SMTP, SendGrid, Resend, etc.).
    """
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    reset_url = f"{frontend_url}/reset-password?token={reset_token}"
    # In a production deployment replace this print with actual email delivery.
    print(f"[AUTH] Password-reset link for {email}:\n  {reset_url}", flush=True)


# =========================================================
# UNIFIED TOKEN RESOLVER
# =========================================================

def resolve_user_id(token: str, google_client_id: Optional[str] = None) -> str:
    """
    Resolve a user_id from either a basic-auth JWT or a Google ID token.

    Tries basic JWT first (fast, no network); falls back to Google OAuth
    verification only when *google_client_id* is provided.

    Raises ValueError when neither path succeeds – the caller is expected
    to convert this to an appropriate HTTP error.
    """
    # --- 1. Basic-auth JWT ---
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        if payload.get("type") == "access" and payload.get("sub"):
            return payload["sub"]
    except Exception:
        pass

    # --- 2. Google OAuth ID token ---
    if google_client_id:
        try:
            from google.auth.transport import requests as grequests  # type: ignore
            from google.oauth2 import id_token as gid_token          # type: ignore

            info = gid_token.verify_oauth2_token(
                token, grequests.Request(), google_client_id
            )
            return info["sub"]
        except Exception:
            pass

    raise ValueError("Unable to resolve user identity from the provided token.")
