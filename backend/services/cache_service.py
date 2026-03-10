"""SQLite 기반 로컬 디스크 캐시 — yfinance API 호출 최소화."""

import sqlite3
import pickle
import time
import os
import threading
import pandas as pd

_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DB_PATH = os.path.join(_DB_DIR, "cache.db")

# 원시 데이터(가격/회사/재무)는 TTL 없이 영구 캐시 — 있으면 사용, 없으면 fetch
# 추천 결과 캐시만 TTL 적용

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """스레드별 SQLite 연결 (thread-safe)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(_DB_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(_DB_PATH, timeout=10)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _init_tables(_local.conn)
    return _local.conn


def _init_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_history (
            ticker TEXT NOT NULL,
            period TEXT NOT NULL,
            interval_ TEXT NOT NULL,
            data BLOB NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (ticker, period, interval_)
        );
        CREATE TABLE IF NOT EXISTS company_info (
            ticker TEXT PRIMARY KEY,
            data BLOB NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS financial_data (
            ticker TEXT PRIMARY KEY,
            data BLOB NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS result_cache (
            key TEXT PRIMARY KEY,
            data BLOB NOT NULL,
            updated_at REAL NOT NULL
        );
    """)
    conn.commit()


# ── 가격 히스토리 ──

def get_cached_history(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    """캐시된 DataFrame 반환. 미스 시 None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT data FROM price_history WHERE ticker=? AND period=? AND interval_=?",
        (ticker, period, interval),
    ).fetchone()
    if row is None:
        return None
    try:
        return pickle.loads(row[0])
    except Exception:
        return None


def set_cached_history(ticker: str, period: str, interval: str, df: pd.DataFrame):
    """DataFrame을 캐시에 저장."""
    conn = _get_conn()
    blob = pickle.dumps(df)
    conn.execute(
        "INSERT OR REPLACE INTO price_history (ticker, period, interval_, data, updated_at) VALUES (?,?,?,?,?)",
        (ticker, period, interval, blob, time.time()),
    )
    conn.commit()


# ── 회사 정보 (stock.info) ──

def get_cached_info(ticker: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT data FROM company_info WHERE ticker=?", (ticker,)
    ).fetchone()
    if row is None:
        return None
    try:
        return pickle.loads(row[0])
    except Exception:
        return None


def set_cached_info(ticker: str, data: dict):
    conn = _get_conn()
    blob = pickle.dumps(data)
    conn.execute(
        "INSERT OR REPLACE INTO company_info (ticker, data, updated_at) VALUES (?,?,?)",
        (ticker, blob, time.time()),
    )
    conn.commit()


# ── 재무 데이터 (stock.financials) ──

def get_cached_financials(ticker: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT data FROM financial_data WHERE ticker=?", (ticker,)
    ).fetchone()
    if row is None:
        return None
    try:
        return pickle.loads(row[0])
    except Exception:
        return None


def set_cached_financials(ticker: str, data: dict):
    conn = _get_conn()
    blob = pickle.dumps(data)
    conn.execute(
        "INSERT OR REPLACE INTO financial_data (ticker, data, updated_at) VALUES (?,?,?)",
        (ticker, blob, time.time()),
    )
    conn.commit()


# ── 결과 캐시 (추천/백테스트 결과 디스크 저장) ──

def get_cached_result(key: str, ttl: int) -> object | None:
    """키 기반 결과 캐시 조회. 만료 시 None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT data, updated_at FROM result_cache WHERE key=?", (key,)
    ).fetchone()
    if row is None:
        return None
    data_blob, updated_at = row
    if time.time() - updated_at > ttl:
        return None
    try:
        return pickle.loads(data_blob)
    except Exception:
        return None


def set_cached_result(key: str, data: object):
    """결과를 디스크 캐시에 저장."""
    conn = _get_conn()
    blob = pickle.dumps(data)
    conn.execute(
        "INSERT OR REPLACE INTO result_cache (key, data, updated_at) VALUES (?,?,?)",
        (key, blob, time.time()),
    )
    conn.commit()


# ── 캐시 관리 ──

def clear_results_cache():
    """결과 캐시만 초기화 (원시 데이터 보존)."""
    conn = _get_conn()
    conn.execute("DELETE FROM result_cache")
    conn.commit()


def clear_all_cache():
    """전체 디스크 캐시 초기화 (원시 데이터 포함)."""
    conn = _get_conn()
    conn.executescript("""
        DELETE FROM price_history;
        DELETE FROM company_info;
        DELETE FROM financial_data;
        DELETE FROM result_cache;
    """)
    conn.commit()


def clear_ticker_cache(ticker: str):
    """특정 종목 캐시 삭제."""
    conn = _get_conn()
    conn.execute("DELETE FROM price_history WHERE ticker=?", (ticker,))
    conn.execute("DELETE FROM company_info WHERE ticker=?", (ticker,))
    conn.execute("DELETE FROM financial_data WHERE ticker=?", (ticker,))
    conn.commit()


def get_cache_stats() -> dict:
    """캐시 통계 반환."""
    conn = _get_conn()
    history_count = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    info_count = conn.execute("SELECT COUNT(*) FROM company_info").fetchone()[0]
    fin_count = conn.execute("SELECT COUNT(*) FROM financial_data").fetchone()[0]

    db_size = 0
    if os.path.exists(_DB_PATH):
        db_size = os.path.getsize(_DB_PATH)

    return {
        "history_entries": history_count,
        "info_entries": info_count,
        "financial_entries": fin_count,
        "db_size_mb": round(db_size / 1024 / 1024, 2),
    }
