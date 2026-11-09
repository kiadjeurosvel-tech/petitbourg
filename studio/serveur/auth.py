"""Authentification : mot de passe unique (PBKDF2), jetons signés HMAC, URL de médias signées.

Aucun secret n'est jamais envoyé au navigateur : il ne reçoit qu'un jeton de session
à durée limitée, et des liens de médias signés valables quelques heures.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque

ITER = 240_000
TOKEN_TTL = 30 * 24 * 3600
MEDIA_TTL = 12 * 3600


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER)
    return f"pbkdf2${ITER}${salt.hex()}${dk.hex()}"


def check_password(pw: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, it, salt, dk = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(got.hex(), dk)
    except ValueError:
        return False


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(secret: bytes, gen: int, ttl=TOKEN_TTL) -> tuple[str, int]:
    exp = int(time.time()) + ttl
    body = _b64(json.dumps({"exp": exp, "gen": gen}).encode())
    sig = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}", exp


def verify_token(secret: bytes, token: str, gen: int) -> bool:
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(secret, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return False
        data = json.loads(_unb64(body))
        return data["exp"] > time.time() and data.get("gen") == gen
    except Exception:  # noqa: BLE001
        return False


def sign_media(secret: bytes, path: str, ttl=MEDIA_TTL) -> str:
    exp = int(time.time()) + ttl
    sig = _b64(hmac.new(secret, f"m|{path}|{exp}".encode(), hashlib.sha256).digest())[:32]
    return f"exp={exp}&sig={sig}"


def verify_media(secret: bytes, path: str, exp: str, sig: str) -> bool:
    try:
        if int(exp) < time.time():
            return False
        good = _b64(hmac.new(secret, f"m|{path}|{int(exp)}".encode(), hashlib.sha256).digest())[:32]
        return hmac.compare_digest(good, sig)
    except (ValueError, TypeError):
        return False


class RateLimiter:
    """5 échecs par minute et par adresse, puis blocage temporaire."""

    def __init__(self, n=5, window=60):
        self.n, self.window = n, window
        self.fail = defaultdict(deque)

    def blocked(self, key: str) -> bool:
        q = self.fail[key]
        now = time.time()
        while q and q[0] < now - self.window:
            q.popleft()
        return len(q) >= self.n

    def failed(self, key: str):
        self.fail[key].append(time.time())
