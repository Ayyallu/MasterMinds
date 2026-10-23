"""Low-level security primitives: password hashing, JWT, token hashing, TOTP."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

_settings = get_settings()
_ph = PasswordHasher()


# --- Passwords ---
def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False
    except Exception:  # malformed/legacy hash — treat as a failed verification
        return False


# --- Access tokens (JWT) ---
def create_access_token(subject: str, claims: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=_settings.access_token_ttl_minutes)).timestamp()
        ),
        "type": "access",
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises jwt exceptions on failure."""
    payload = jwt.decode(
        token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm]
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return payload


# --- Refresh / reset tokens (opaque, stored hashed) ---
def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- TOTP (MFA) ---
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_name: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name, issuer_name=_settings.totp_issuer
    )


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)
