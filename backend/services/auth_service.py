"""사용자 인증 서비스 (SQLite + JWT)."""

import os
import sqlite3
import hashlib
import secrets
import time
import jwt
from datetime import datetime, timedelta

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DB_PATH = os.path.join(_DATA_DIR, "users.db")
_JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 24 * 7  # 7일


def _get_conn() -> sqlite3.Connection:
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            display_name TEXT,
            kakao_id TEXT UNIQUE,
            profile_image TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # 카카오 컬럼 마이그레이션
    for col, ctype in [("kakao_id", "TEXT"), ("profile_image", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ctype}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def _hash_password(password: str, salt: str) -> str:
    """SHA-256 해시 (salt + password)."""
    return hashlib.sha256((salt + password).encode()).hexdigest()


def register(username: str, password: str, display_name: str = "") -> dict:
    """회원가입."""
    username = username.strip().lower()
    if len(username) < 3:
        return {"error": "아이디는 3자 이상이어야 합니다"}
    if len(password) < 4:
        return {"error": "비밀번호는 4자 이상이어야 합니다"}

    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)

    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, display_name) VALUES (?, ?, ?, ?)",
            (username, pw_hash, salt, display_name or username),
        )
        conn.commit()
        user_id = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]
        conn.close()
        token = _create_token(user_id, username)
        return {"token": token, "user": {"id": user_id, "username": username, "display_name": display_name or username}}
    except sqlite3.IntegrityError:
        conn.close()
        return {"error": "이미 존재하는 아이디입니다"}


def login(username: str, password: str) -> dict:
    """로그인."""
    username = username.strip().lower()
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()

    if not row:
        return {"error": "아이디 또는 비밀번호가 올바르지 않습니다"}

    pw_hash = _hash_password(password, row["salt"])
    if pw_hash != row["password_hash"]:
        return {"error": "아이디 또는 비밀번호가 올바르지 않습니다"}

    token = _create_token(row["id"], row["username"])
    return {
        "token": token,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"] or row["username"],
        },
    }


def _create_token(user_id: int, username: str) -> str:
    """JWT 토큰 생성."""
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=_JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """JWT 토큰 검증. 성공 시 payload 반환, 실패 시 None."""
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_user(user_id: int) -> dict | None:
    """사용자 정보 조회."""
    conn = _get_conn()
    row = conn.execute("SELECT id, username, display_name, profile_image, created_at FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def kakao_login(kakao_id: str, nickname: str, profile_image: str = "") -> dict:
    """카카오 OAuth 로그인/회원가입."""
    kakao_id = str(kakao_id)
    conn = _get_conn()

    # 기존 카카오 유저 확인
    row = conn.execute("SELECT * FROM users WHERE kakao_id=?", (kakao_id,)).fetchone()

    if row:
        # 기존 유저 — 프로필 업데이트
        conn.execute(
            "UPDATE users SET display_name=?, profile_image=? WHERE id=?",
            (nickname or row["display_name"], profile_image, row["id"]),
        )
        conn.commit()
        user_id = row["id"]
        username = row["username"]
        display_name = nickname or row["display_name"]
    else:
        # 신규 — 자동 회원가입
        username = f"kakao_{kakao_id}"
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(secrets.token_hex(8), salt)  # 랜덤 비밀번호
        display_name = nickname or f"User {kakao_id[-4:]}"

        try:
            conn.execute(
                """INSERT INTO users (username, password_hash, salt, display_name, kakao_id, profile_image)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, pw_hash, salt, display_name, kakao_id, profile_image),
            )
            conn.commit()
            user_id = conn.execute("SELECT id FROM users WHERE kakao_id=?", (kakao_id,)).fetchone()["id"]
        except sqlite3.IntegrityError:
            conn.close()
            return {"error": "계정 생성 실패"}

    conn.close()
    token = _create_token(user_id, username)
    return {
        "token": token,
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "profile_image": profile_image,
        },
    }
